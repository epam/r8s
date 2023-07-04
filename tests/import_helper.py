import os
import sys
from pathlib import Path

SRC_FOLDER = 'src'


def add_src_to_path():
    """
    Add the folder with test_lambdas and all the dependencies to path in order
    to make them available for importing while conducting the tests.
    """
    project_path = Path(__file__).parent.parent
    src_path = Path(project_path, SRC_FOLDER)
    if os.path.exists(src_path):
        src_path = str(src_path)
        if src_path not in sys.path:
            sys.path.append(src_path)
    else:
        print(f"Src path {src_path} doesn't seem to exist. "
              f"Tests cannot be conducted", file=sys.stderr)
        sys.exit(1)
