import pytest
from unittest.mock import patch
from typing import Any
from src.utils.manage_argument_parser import ManageParser


def test_invalid_log_level_logs_and_exits(capsys: Any) -> None:
    with patch("sys.argv", ". user_sync --console banana".split()):
        with pytest.raises(SystemExit):
            ManageParser().parse_cli_args()
        captured = capsys.readouterr()
        assert "banana" in captured.err


def test_default_console_log_level() -> None:
    with patch(
        "sys.argv",
        ". user_sync --config_file bla ".split(),
    ):
        args = ManageParser().parse_cli_args()
        assert args.console_log_level == "INFO"


def test_specific_console_log_level() -> None:
    with patch(
        "sys.argv",
        ". user_sync --cons debug --config_file bla ".split(),
    ):
        args = ManageParser().parse_cli_args()
        assert args.console_log_level == "DEBUG"
