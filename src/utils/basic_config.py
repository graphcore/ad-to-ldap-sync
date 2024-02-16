"""This module is used to set up all the basic configuration for later use."""

from loguru import logger
import yaml
import sys
from utils.manage_argument_parser import ManageArguments
from typing import Any


class BasicConfig:
    """
    This class is used to set up all the basic configuration for later use.
    """

    def __init__(self, args: ManageArguments) -> None:
        """Initialization of the class."""
        self.args = args

    def _load_yaml_file(self, yaml_file: str) -> Any:
        """Load the requested YAML file.

        Parameters
        ----------
        yaml_file :
            The path of the file to load.

        Returns
        -------
        Dictionary of the loaded YAML file.
        """
        try:
            with open(yaml_file, "r") as stream:
                return yaml.safe_load(stream)
        except Exception as exc:
            logger.error("Unable to open file:")
            logger.error(exc)
            self.run_status = False
            sys.exit(1)

    def _load_exception_file(self, exception_file: str) -> Any:
        """Load the exceptions YAML file.

        Returns
        -------
        Dictionary of the loaded YAML file.
        """
        return self._load_yaml_file(exception_file)

    def _load_config_file(self) -> Any:
        """Load the main configuration YAML file.

        Returns
        -------
        Dictionary of the loaded YAML file.
        """
        config = self._load_yaml_file(self.args.config_file)
        if config:
            return config
        else:
            logger.error("Empty config file!!!")
            sys.exit(1)

    def _load_country_control_file(self, country_control_file: str) -> Any:
        """Load the country control YAML file.

        Returns
        -------
        Dictionary of the loaded YAML file.
        """
        return self._load_yaml_file(country_control_file)

    def create_basic_config(self) -> dict[str, Any]:
        """Main function of the class."""
        config = self._load_config_file()
        exceptions = self._load_exception_file(config["settings"]["exception_file"])
        country_control = self._load_country_control_file(
            config["settings"]["country_control_file"]
        )
        return {
            "config": config,
            "exceptions": exceptions,
            "country_control": country_control,
            "args": self.args,
        }
