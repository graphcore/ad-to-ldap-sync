"""This module is used to set up the argument parser."""
from argparse import ArgumentParser
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ManageArguments:
    """
    The data class for all the arguments.
    """

    config_file: str
    console_log_level: str
    universal_override: bool
    group_override: list[str]
    op_type: str
    environment: str


class ManageParser:
    """
    This class is used to set up the argument parser.
    """

    @staticmethod
    def _add_environment(parser: ArgumentParser) -> None:
        """Add environment."""
        parser.add_argument(
            "--environment",
            type=str,
            help="Environment to operate in. Default: noop",
            default="noop",
            choices=[
                "noop",
                "prod",
            ],
        )

    @staticmethod
    def _add_config_file(parser: ArgumentParser) -> None:
        """Add main configuration file argument."""
        parser.add_argument(
            "--config_file",
            type=str,
            help="Config file.",
            default="config/config.yaml",
        )

    @staticmethod
    def _add_group_override(parser: ArgumentParser) -> None:
        """Add group override argument."""
        parser.add_argument(
            "--group_override",
            nargs="*",
            default=[],
            help="A list of groups to override.",
        )

    @staticmethod
    def _add_universal_override(parser: ArgumentParser) -> None:
        """Add universal override argument."""
        parser.add_argument(
            "--universal_override",
            default=False,
            action="store_true",
            help=(
                "!!! WARNING !!!"
                "Modifies ALL groups regardless of override requirements."
                "Please consider using '--group' for specific group overrides."
            ),
        )

    @staticmethod
    def _add_console_log_level(parser: ArgumentParser) -> None:
        """Add console log level argument."""
        parser.add_argument(
            "--console_log_level",
            type=str,
            choices=["error", "warning", "info", "debug"],
            default="info",
            help="Console level configuration (default: %(default)s).",
        )

    def _build_parser(self) -> ArgumentParser:
        """Build the argument parser.

        Returns
        -------
        ArgumentParser object with all relevant arguments.
        """
        parser = ArgumentParser()
        subparsers = parser.add_subparsers(
            title="Operational types", required=True, dest="op_type"
        )
        group_sync_parser = subparsers.add_parser(
            "group_sync", help="Perform group synchronization."
        )
        user_sync_parser = subparsers.add_parser(
            "user_sync", help="Perform user synchronization."
        )
        # User synchronization
        self._add_config_file(user_sync_parser)
        self._add_console_log_level(user_sync_parser)
        self._add_environment(user_sync_parser)
        # Group synchronization
        self._add_config_file(group_sync_parser)
        self._add_console_log_level(group_sync_parser)
        self._add_universal_override(group_sync_parser)
        self._add_group_override(group_sync_parser)
        self._add_environment(group_sync_parser)

        return parser

    def parse_cli_args(self) -> ManageArguments:
        """Parse the arguments.

        Returns
        -------
        ManageArguments object with all relevant arguments.
        """
        return self._parse_args()

    def _parse_args(self) -> ManageArguments:
        """Parse the arguments.

        Returns
        -------
        ManageArguments object with all relevant arguments.
        """
        return self._build_args(vars(self._build_parser().parse_args()))

    @staticmethod
    def _build_args(args: Dict[str, Any]) -> ManageArguments:
        """Build the arguments.

        Returns
        -------
        ManageArguments object with all relevant arguments.
        """
        return ManageArguments(
            config_file=str(args.get("config_file")),
            console_log_level=str(args.get("console_log_level")).upper(),
            universal_override=bool(args.get("universal_override")),
            group_override=args.get("group_override"),  # type: ignore
            op_type=str(args.get("op_type")),
            environment=str(args.get("environment")),
        )
