import os

from typer.testing import CliRunner

from infrahub_ctl.utils import get_fixtures_dir
from infrahub_ctl.validate import app

runner = CliRunner()


def test_validate_schema_valid():
    fixture_file = os.path.join(get_fixtures_dir(), "models", "valid_model_01.json")

    result = runner.invoke(app=app, args=["schema", fixture_file])
    assert result.exit_code == 0
    assert "Schema is valid" in result.stdout


def test_validate_schema_non_valid():
    fixture_file = os.path.join(get_fixtures_dir(), "models", "non_valid_model_01.json")

    result = runner.invoke(app=app, args=["schema", fixture_file])
    assert result.exit_code == 2
    assert "Schema not valid" in result.stdout


def test_validate_schema_json_non_valid():
    fixture_file = os.path.join(get_fixtures_dir(), "models", "non_valid_json_01.json")

    result = runner.invoke(app=app, args=["schema", fixture_file])
    assert result.exit_code == 2
    assert "Invalid JSON file" in result.stdout
