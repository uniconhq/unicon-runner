import abc
from enum import Enum
from itertools import groupby
from typing import Any, Generic, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from unicon_runner.executor.variants.base import Executor, Result
from unicon_runner.lib.common import CustomBaseModel
from unicon_runner.schemas import (
    File,
    ProgrammingEnvironment,
    Request,
    Status,
    TaskEvalResult,
    TaskEvalStatus,
)


class TestcaseResult(BaseModel):
    status: int
    stdout: str
    stderr: str


class RunnerResponse(BaseModel):
    # Reference: https://github.com/uniconhq/unicon-runner/blob/main/unicon_runner/executor/run.py#L69-L73
    submission_id: str
    testcase_results: list[TestcaseResult]


async def run_program(
    files: list[File],
    environment: ProgrammingEnvironment,
    entrypoint: str,
    executor: Executor,
) -> RunnerResponse:
    executor_resp = await executor.run_request(
        request=Request(files=files, environment=environment, entrypoint=entrypoint),
        request_id=str(uuid4()),
    )

    return executor_resp


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"
    EXTRACT_PROGRAM_OUTPUT = "EXTRACT_PROGRAM_OUTPUT_STEP"
    STRING_MATCH = "STRING_MATCH_STEP"


StepInputType = TypeVar("StepInputType")
StepExpectedAnswer = TypeVar("StepExpectedAnswer")
StepOutputType = TypeVar("StepOutputType")

type Unused = None


class Step(
    CustomBaseModel,
    abc.ABC,
    Generic[StepInputType, StepExpectedAnswer, StepOutputType],
    polymorphic=True,
):
    id: int
    type: StepType

    @abc.abstractmethod
    async def run(
        self,
        user_input: StepInputType,
        expected_answer: StepExpectedAnswer,
        environment: ProgrammingEnvironment,
        executor: Executor,
    ) -> StepOutputType:
        pass


class ExtractProgramOutputStep(Step[RunnerResponse, Unused, str]):
    key: Literal["stdout", "stderr", "status"]

    async def run(self, user_input: RunnerResponse, *__unused_args) -> str:
        return getattr(user_input, self.key)


class StringMatchStep(Step[str, str, bool]):
    async def run(self, input: str, expected_answer: str, *__unused_args) -> bool:
        print(repr(input), repr(expected_answer))
        return input == expected_answer


class PyRunFunctionStep(Step[list[File], Unused, RunnerResponse]):
    file_name: str
    function_name: str
    arguments: list[int | str]
    keyword_arguments: dict[str, str]

    async def run(
        self,
        user_input: list[File],
        _: Unused,
        environment: ProgrammingEnvironment,
        executor: Executor,
    ) -> RunnerResponse:
        def stringify_arg(arg: int | str) -> str:
            # Integers are passed as-is, strings are wrapped in double quotes
            return str(arg) if isinstance(arg, int) else f'"{arg}"'

        if not any(f.file_name == self.file_name for f in user_input):
            raise ValueError(f"File {self.file_name} not found in input files")

        func_args_kwargs = [stringify_arg(arg) for arg in self.arguments] + [
            f"{k}={stringify_arg(v)}" for k, v in self.keyword_arguments.items()
        ]
        func_invocation = f"{self.function_name}({', '.join(func_args_kwargs)})"
        # TODO: Remove dependence on `print` and `stdout`
        assembled_code = f"from {self.file_name.split(".py")[0]} import {self.function_name}\n\nprint({func_invocation})"

        return await run_program(
            user_input + [File(file_name="__run.py", content=assembled_code)],
            environment,
            "__run.py",
            executor,
        )


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class Testcase(BaseModel):
    id: int
    steps: list[Step]

    async def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
        environment: ProgrammingEnvironment,
        executor: Executor,
    ):
        expected_answer_by_step = {
            step_expected_answer.step_id: step_expected_answer.expected_answer
            for step_expected_answer in expected_answer
        }

        # TEMP: Assume that steps are a linear sequence and run them in order
        step_idx: int = 0
        prev_step_output: Any = user_input

        results = Result(status=Status.OK, stdout="", stderr="")

        while step_idx < len(self.steps):
            step = self.steps[step_idx]

            step_expected_answer = expected_answer_by_step.get(step.id)
            step_output = await step.run(
                prev_step_output, step_expected_answer, environment, executor
            )

            print(f"Step {step.id} [{step.type}] output: {step_output}")

            if step.type == StepType.PY_RUN_FUNCTION:
                results = step_output
            elif step.type == StepType.STRING_MATCH and step_output is False:
                results.status = Status.WA

            if results.status != Status.OK:
                return results
            prev_step_output = step_output
            step_idx += 1

        return results


class TaskType(str, Enum):
    PROGRAMMING = "PROGRAMMING_TASK"


class ProgrammingTask(BaseModel):
    submission_id: str
    environment: ProgrammingEnvironment
    templates: list[File]
    testcases: list[Testcase]
    user_input: list[File]
    expected_answer: list[ProgrammingTaskExpectedAnswer]

    async def run(self, executor: Executor) -> TaskEvalResult[bool]:
        expected_answer_by_testcase = {
            testcase_id: list(group)
            for testcase_id, group in groupby(self.expected_answer, lambda x: x.testcase_id)
        }

        results = []
        for testcase in self.testcases:
            testcase_expected_answer = expected_answer_by_testcase.get(testcase.id)
            if not testcase_expected_answer:
                print(f"WARN: Testcase {testcase.id} has no expected answer")
                continue
            results.append(
                await testcase.run(
                    self.user_input,
                    testcase_expected_answer,
                    self.environment,
                    executor,
                )
            )

        # TODO: check output and handle pending testcases
        return TaskEvalResult(
            submission_id=self.submission_id,
            status=TaskEvalStatus.SUCCESS,
            result=results,
        )
