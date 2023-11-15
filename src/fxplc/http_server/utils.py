from typing import Any

import yaml


def read_yaml_file(path: str) -> Any:
    with open(path, "rt") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)
