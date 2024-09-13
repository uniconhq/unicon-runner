from unicon_runner.schemas import Request
import subprocess
from uuid import uuid4
import os
import glob

from jinja2 import Environment, FileSystemLoader, select_autoescape
env = Environment(loader=FileSystemLoader("unicon_runner/executor/templates"),
                  autoescape=select_autoescape())
dockerfile_template = env.get_template("Dockerfile.jinja")


def run_request(request: Request):
    # 1. Generate temp folder name
    folder_name = str(uuid4()).replace("-", "")
    folder_path = os.path.join("temp", folder_name)
    os.mkdir(folder_path)

    # 2. Create files
    for file in request.files:
        with open(os.path.join(folder_path, file.file_name), "w") as f:
            f.write(file.content)

    with open(os.path.join(folder_path, "Dockerfile"), "w") as f:
        dockerfile = dockerfile_template.render(entrypoint=request.entrypoint)
        f.write(dockerfile)

    # 3. Spawn podman container
    subprocess.run(["podman", "build", os.path.join(
        folder_path), "-t", folder_name], capture_output=True, text=True)

    result = subprocess.run(["podman", "run", "--name", folder_name + "_run", folder_name],
                            capture_output=True, text=True)

    # 4. Output raw result
    stdout = result.stdout
    stderr = result.stderr

    # 5. Clean up folders
    files = glob.glob(os.path.join(folder_path, "*"))
    for f in files:
        os.remove(f)
    os.rmdir(folder_path)

    return {
        "stdout": stdout,
        "stderr": stderr
    }
