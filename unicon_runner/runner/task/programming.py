import abc
from collections import defaultdict
from enum import Enum
from functools import cached_property
from itertools import groupby
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from unicon_runner.executor.base import Executor
from unicon_runner.lib.common import CustomBaseModel
from unicon_runner.lib.graph import Graph, GraphEdge, GraphNode
from unicon_runner.runner.runner import RunnerType
from unicon_runner.schemas import (
    File,
    ProgrammingEnvironment,
    Request,
    TaskEvalResult,
    TaskEvalStatus,
)


class StepType(str, Enum):
    PY_RUN_FUNCTION = "PY_RUN_FUNCTION_STEP"
    STRING_MATCH = "STRING_MATCH_STEP"
    INPUT = "INPUT_STEP"
    OUTPUT = "OUTPUT_STEP"
    CONSTANT = "CONSTANT_STEP"
    EXTRACT_PROGRAM_OUTPUT = "EXTRACT_PROGRAM_OUTPUT_STEP"
    PARAMS_WITHOUT_KEYWORD_ARGS = "PARAMS_WITHOUT_KEYWORD_ARGS_STEP"
    SUBGRAPH_INIT = "SUBGRAPH_INIT_STEP"
    BREAKING_CONDITION = "BREAKING_CONDITION_STEP"


StepInputType = TypeVar("StepInputType")
StepExpectedAnswer = TypeVar("StepExpectedAnswer")
StepOutputType = TypeVar("StepOutputType")

type Unused = None

type ProgramFragment = str
type ProgramVariable = str
type SocketName = str


class Socket(BaseModel):
    id: int
    name: str


class Step(CustomBaseModel, GraphNode, abc.ABC, polymorphic=True):
    id: int
    type: StepType

    subgraph: "StepGraph" | None = None

    def get_comment_header(self):
        return f"# Step {self.id}: {self.type.value}"

    @abc.abstractmethod
    def get_code(self, inputs: dict[SocketName, ProgramVariable]) -> ProgramFragment:
        pass


class StepGraph(Graph[Step]):
    @cached_property
    def node_index(self) -> dict[int, Step]:
        return {step.id: step for step in self.nodes}

    @cached_property
    def in_link_index(self) -> dict[int, list[GraphEdge]]:
        in_link_index: dict[int, list[GraphEdge]] = defaultdict(list)
        for link in self.edges:
            in_link_index[link.to_node_id].append(link)
        return in_link_index

    def assemble_program(self, user_input: list[File]) -> ProgramFragment:
        code_components: list[str] = []

        # Steps are already in topological order so we can just run them in order
        for step in self.nodes:
            # Output of a step will be stored in a variable in the format `var_{step_id}_{socket_id}`
            # It is assumed that every step will always output the same number of values as the number of output sockets
            # As such, all we need to do is to pass in the correct variables to the next step

            # TEMP: Handle user input for PyRunFunctionStep
            if isinstance(step, PyRunFunctionStep):
                step.set_user_input(user_input)

            input_variables: dict[str, Any] = {}

            for in_link in self.in_link_index[step.id]:
                in_node = self.node_index[in_link.from_node_id]
                # Find the socket that the link is connected to
                for socket in filter(lambda socket: socket.id == in_link.to_socket_id, step.inputs):
                    input_variables[socket.name] = f"var_{in_node.id}_{in_link.from_socket_id}"

            code_components.append(step.get_code(input_variables))

        assembled_program: str = "\n\n".join(code_components)
        # TEMP: for debugging
        print(assembled_program)
        return assembled_program


class ConstantStep(Step):
    values: dict[str, Any]

    def get_code(self, *__unused_args) -> ProgramFragment:
        code: list[ProgramFragment] = [self.get_comment_header()]

        for output in self.outputs:
            value = self.values[output.name]
            code.append(f"var_{self.id}_{output.id} = {value}")

        return "\n".join(code)


class ExtractProgramOutputStep(Step):
    key: str

    def get_code(self, inputs: dict[SocketName, ProgramVariable]) -> ProgramFragment:
        input_variables = list(inputs.values())
        assert len(input_variables) == 1
        input_variable = input_variables[0]

        assert len(self.outputs) == 1
        output = self.outputs[0]

        code = [self.get_comment_header()]
        code.append(f"var_{self.id}_{output.id} = {input_variable}['{self.key}']")

        return "\n".join(code)


class ParamsWithoutKeywordArgsStep(Step):
    def get_code(self, inputs: dict[SocketName, ProgramVariable]) -> ProgramFragment:
        input_variables = list(inputs.values())
        assert len(input_variables) == len(self.inputs)

        assert len(self.outputs) == 1
        output = self.outputs[0]

        code = [self.get_comment_header()]
        code.append(
            f"var_{self.id}_{output.id} = {{'arguments': [{", ".join(input_variables)}], 'keyword_arguments': {{}}}}"
        )

        return "\n".join(code)


class InputStep(Step):
    values: dict

    def get_code(self, *__unused_args) -> ProgramFragment:
        code = [self.get_comment_header()]

        for output in self.outputs:
            value = self.values[output.name]
            code.append(f"var_{self.id}_{output.id} = {value}")

        return "\n".join(code)


class OutputStep(Step):
    def get_code(self, inputs: dict[SocketName, ProgramVariable]) -> ProgramFragment:
        code = [self.get_comment_header(), "import json"]

        result = (
            "{"
            + ", ".join((f'"{key}": {variable_name}' for key, variable_name in inputs.items()))
            + "}"
        )
        code.append(f"print(json.dumps({result}))")

        return "\n".join(code)


class StringMatchStep(Step):
    def get_code(self, inputs: dict[SocketName, ProgramVariable]) -> ProgramFragment:
        output = self.outputs[0]
        output_variable = f"var_{self.id}_{output.id}"

        input_variables = list(inputs.values())
        assert len(input_variables) == 2

        code = [self.get_comment_header()]
        code.append(f"{output_variable} = str({input_variables[0]}) == str({input_variables[1]})")

        return "\n".join(code)


class Params(BaseModel):
    arguments: list[int | str]
    keyword_arguments: dict[str, str]


class PyRunFunctionStep(Step):
    file_name: str
    function_name: str
    params: Params | None = None
    user_input: list[File] | None = []

    def set_user_input(self, user_input: list[File]):
        self.user_input = user_input

    def get_code(self, inputs: dict):
        # Precondition: set_user_input has been called
        assert self.user_input is not None

        if not any([f.file_name == self.file_name for f in self.user_input]):
            raise ValueError(f"File {self.file_name} not found in input files")

        assert len(inputs) == 1
        params_variable = list(inputs.values())[0]

        func_invocation = f"{self.function_name}(*{params_variable}['arguments'], **{params_variable}['keyword_arguments'])"
        # TODO: Remove dependence on `print` and `stdout`
        output = self.outputs[0]
        output_variable = f"var_{self.id}_{output.id}"
        assembled_code = f"from {self.file_name.split(".py")[0]} import {self.function_name}\n\n{output_variable} = {func_invocation}"
        return self.get_comment_header() + "\n" + assembled_code


class ProgrammingTaskExpectedAnswer(BaseModel):
    testcase_id: int
    step_id: int
    expected_answer: Any


class SubgraphInitStep(Step):
    """
    This node's purpose is to allow the subgraph to set the state variable
    so that the state in subgraph.run() can properly propagate to the other nodes.
    """

    # TODO: implement
    state_variable: str | None = None

    def set_state_variable(self, state_variable: str):
        self.state_variable = state_variable

    def get_code(self, *__unused_args):
        assert self.state_variable is not None
        assert len(self.outputs) == 1

        output = self.outputs[0]
        output_variable = f"var_{self.id}_{output.id}"
        return self.get_comment_header() + "\n" + f"{output_variable} = {self.state_variable}"


class BreakingConditionStep(Step):
    """This should output:

    def <breaking_condition>():
        ...

    if <breaking_condition>(state):
        break
    """

    function_name: str
    function_code: str

    def get_code(self, inputs: dict):
        code = [self.get_comment_header()]

        input_variables = list(inputs.values())
        assert len(input_variables) == 1
        state_variable = f"var_{self.id}_state"

        code.append(self.function_code)
        code.append(f"if {self.function_name}({state_variable}):\n\tbreak")
        return "\n".join(code)


class LoopStep(Step):
    breaking_condition: BreakingConditionStep
    user_input: list[File] | None = None

    def set_user_input(self, user_input: list[File]):
        self.user_input = user_input

    def get_code(self, inputs: dict):
        assert self.user_input is not None
        assert self.subgraph is not None

        code = [self.get_comment_header()]

        # First, define a state variable. set it to inputs, there should be one
        input_variables = list(inputs.values())
        assert len(input_variables) == 1
        state_variable = f"var_{self.id}_state"
        code.append(f"{state_variable} = {input_variables[0]}")

        # while True
        code.append("while True:")

        # call breaking condition
        code.append(self.breaking_condition.get_code({"state": state_variable}))

        # pass in the subgraph
        ## first pass state_variable to loopinit node
        subgraph_init_step = self.subgraph.nodes[0]
        assert isinstance(subgraph_init_step, SubgraphInitStep)
        subgraph_init_step.set_state_variable(state_variable)

        ## get subgraph code
        subgraph_code = self.subgraph.assemble_program(self.user_input)

        ## indent subgraph code
        subgraph_code.replace("\n", "\n\t")

        # TODO: find output variable of output step
        subgraph_output_steps = [
            step for step in self.subgraph.nodes if step.type == StepType.OUTPUT
        ]
        assert len(subgraph_output_steps) == 1
        subgraph_output_step = subgraph_output_steps[0]

        subgraph_output_variable = f"var_{subgraph_output_step.outputs[0].id}_1"

        # set state to this variable
        subgraph_code += f"\n\t{state_variable} = {subgraph_output_variable}"

        code.append(subgraph_code)
        return "\n".join(code)


class Testcase(StepGraph):
    id: int

    async def run(
        self,
        user_input: list[File],
        expected_answer: list[ProgrammingTaskExpectedAnswer],
        environment: ProgrammingEnvironment,
        executor: Executor,
    ):
        # TODO: figure out what to do with this variable
        expected_answer_by_step = {  # noqa: F841
            step_expected_answer.step_id: step_expected_answer.expected_answer
            for step_expected_answer in expected_answer
        }

        return await executor.run_request(
            request=Request(
                files=user_input
                + [File(file_name="__run.py", content=self.assemble_program(user_input))],
                environment=environment,
                entrypoint="__run.py",
            ),
            request_id=str(uuid4()),
        )


class ProgrammingTask(BaseModel):
    submission_id: str
    environment: ProgrammingEnvironment
    executor_type: RunnerType | None = None

    templates: list[File]
    testcases: list[Testcase]
    user_input: list[File]
    expected_answer: list[ProgrammingTaskExpectedAnswer]

    async def run(self, executor: Executor) -> TaskEvalResult[list[Any]]:
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

        return TaskEvalResult(
            submission_id=self.submission_id,
            status=TaskEvalStatus.SUCCESS,
            result=results,
        )
