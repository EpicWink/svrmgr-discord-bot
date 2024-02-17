"""Build Lambda function deployment package."""

import pathlib
import shutil
import subprocess
import sys

root_dir = pathlib.Path(__file__).parent.parent

build_dir = root_dir / "build"
print(f"Creating build directory: {build_dir}", file=sys.stderr)
build_dir.mkdir(exist_ok=False)

requirements_file = root_dir / "app.requirements.txt"
print(f"Installing dependencies from: {requirements_file}", file=sys.stderr)
subprocess.run([
    sys.executable, "-m", "pip",
    "install",
    "--no-compile",
    "--only-binary=:all:",
    "--platform", "manylinux2014_x86_64",
    "--python-version", "3.12",
    "--implementation", "cp",
    "--requirement", str(requirements_file),
    "--target", str(build_dir),
], check=True)  # fmt: skip

source_dir = root_dir / "src"
print(f"Copying source from: {source_dir}", file=sys.stderr)
shutil.copytree(source_dir, build_dir, dirs_exist_ok=True)

zip_basename_path = build_dir / "dist"
print(f"Zipping build directory to: {zip_basename_path}.zip")
shutil.make_archive(
    base_name=str(zip_basename_path),
    format="zip",
    root_dir=build_dir,
    base_dir=build_dir,
)
