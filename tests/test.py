import pathlib
import sys

import moto

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "src"))

import main


@moto.mock_aws
def test() -> None:
    pass
