import glob
import os
from pathlib import Path
from typing import List, Optional, Union

import pendulum
import yaml
from git import Repo
from pendulum.datetime import DateTime
from rich.console import Console
from rich.markup import escape

from infrahub_ctl.exceptions import FileNotValidError, QueryNotFoundError


def print_graphql_errors(console: Console, errors: List) -> None:
    if not isinstance(errors, list):
        console.print(f"[red]{escape(str(errors))}")

    for error in errors:
        if isinstance(error, dict) and "message" in error and "path" in error:
            console.print(f"[red]{escape(str(error['path']))} {escape(str(error['message']))}")
        else:
            console.print(f"[red]{escape(str(error))}")


def load_repository_config_file(repo_config_file: Path) -> dict:
    if not repo_config_file.is_file():
        raise FileNotFoundError(repo_config_file)

    try:
        yaml_data = repo_config_file.read_text()
        data = yaml.safe_load(yaml_data)
    except yaml.YAMLError as exc:
        raise FileNotValidError(name=str(repo_config_file)) from exc

    return data


def parse_cli_vars(variables: Optional[List[str]]) -> dict:
    if not variables:
        return {}

    return {var.split("=")[0]: var.split("=")[1] for var in variables if "=" in var}


def calculate_time_diff(value: str) -> Optional[str]:
    """Calculate the time in human format between a timedate in string format and now."""
    try:
        time_value = pendulum.parse(value)
    except pendulum.parsing.exceptions.ParserError:
        return None

    if not isinstance(time_value, DateTime):
        return None

    pendulum.set_locale("en")
    return time_value.diff_for_humans(other=pendulum.now(), absolute=True)


def find_graphql_query(name: str, directory: Union[str, Path] = ".") -> str:
    for query_file in glob.glob(f"{directory}/**/*.gql", recursive=True):
        filename = os.path.basename(query_file)
        query_name = os.path.splitext(filename)[0]

        if query_name != name:
            continue
        with open(query_file, "r", encoding="UTF-8") as file_data:
            query_string = file_data.read()

        return query_string

    raise QueryNotFoundError(name=name)


def find_files(
    extension: Union[str, List[str]], directory: Union[str, Path] = ".", recursive: bool = True
) -> List[str]:
    files = []

    if isinstance(extension, str):
        files.extend(glob.glob(f"{directory}/**/*.{extension}", recursive=recursive))
        files.extend(glob.glob(f"{directory}/**/.*.{extension}", recursive=recursive))
    elif isinstance(extension, list):
        for ext in extension:
            files.extend(glob.glob(f"{directory}/**/*.{ext}", recursive=recursive))
            files.extend(glob.glob(f"{directory}/**/.*.{ext}", recursive=recursive))
    return files


def render_action_rich(value: str) -> str:
    if value == "created":
        return f"[green]{value.upper()}[/green]"
    if value == "updated":
        return f"[magenta]{value.upper()}[/magenta]"
    if value == "deleted":
        return f"[red]{value.upper()}[/red]"

    return value.upper()


def get_branch(branch: Optional[str] = None, directory: Union[str, Path] = ".") -> str:
    """If branch isn't provide, return the name of the local Git branch."""
    if branch:
        return branch

    repo = Repo(directory)
    return str(repo.active_branch)


def get_fixtures_dir() -> Path:
    """Get the directory which stores fixtures that are common to multiple unit/integration tests."""
    here = os.path.abspath(os.path.dirname(__file__))
    fixtures_dir = os.path.join(here, "..", "tests", "fixtures")

    return Path(os.path.abspath(fixtures_dir))
