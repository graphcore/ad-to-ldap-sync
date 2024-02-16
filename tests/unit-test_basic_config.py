# type: ignore
import logging
import os
import yaml
import pytest
from loguru import logger
from src.utils.basic_config import BasicConfig
from unittest.mock import MagicMock
from _pytest.logging import caplog as _caplog  # noqa

CONFIG_FILE = "tests/data/test_config.yaml"
EXCEPTIONS_FILE = "tests/data/test_exceptions.yaml"
COUNTRY_CONTROL_FILE = "tests/data/test_country_control.yaml"
EMPTY_CONFIG_FILE = "tests/data/test_config_empty.yaml"


@pytest.fixture
def caplog(_caplog):  # noqa
    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message} {extra}")
    yield _caplog
    logger.remove(handler_id)


class TestBasicConfig:
    @classmethod
    def setup_class(self):
        self.args = MagicMock()
        self.basic_config = {}
        self.config = yaml.safe_load(open(CONFIG_FILE, "r"))
        self.empty_config = yaml.safe_load(open(EMPTY_CONFIG_FILE, "r"))
        self.exceptions = yaml.safe_load(open(EXCEPTIONS_FILE, "r"))
        self.country_control = yaml.safe_load(open(COUNTRY_CONTROL_FILE, "r"))

    def setup_method(self):
        self.mocked_obj = MagicMock()
        self.mocked_openldap_connection = MagicMock()
        self.mocked_ad_connection = MagicMock()
        self.ldap_connections = {
            "ad": self.mocked_ad_connection,
            "openldap": self.mocked_openldap_connection,
        }
        self.args.console_log_level = "INFO"
        self.args.config_file = CONFIG_FILE
        self.args.exception_file = EXCEPTIONS_FILE
        self.args.country_control_file = COUNTRY_CONTROL_FILE
        self.args.op_type = "unit-test-user-sync"
        self.args.environment = "noop"
        self.basic_config = {
            "config": self.config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }

    def teardown_method(self):
        self.remove_file(
            f"{self.args.op_type}_"
            f"{self.basic_config['config']['settings']['log_file']}"
        )

    @staticmethod
    def remove_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def test_create_basic_config(self) -> None:
        self.mocked_obj._load_config_file = MagicMock(return_value=self.config)
        self.mocked_obj._load_exception_file = MagicMock(return_value=self.exceptions)
        self.mocked_obj._load_country_control_file = MagicMock(
            return_value=self.country_control
        )
        returned_basic_config = BasicConfig.create_basic_config(self.mocked_obj)
        assert returned_basic_config["config"] == self.config
        assert returned_basic_config["exceptions"] == self.exceptions
        assert returned_basic_config["country_control"] == self.country_control

    def test_load_yaml_file_good(self) -> None:
        returned_config = BasicConfig._load_yaml_file(self.mocked_obj, CONFIG_FILE)
        assert returned_config == self.config

    def test_load_yaml_file_broken_syntax(self, caplog) -> None:
        broken_config_file = "tests/data/test_broken_syntax.yaml"
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                BasicConfig._load_yaml_file(self.mocked_obj, broken_config_file)
        assert len(caplog.text) > 0

    def test_load_yaml_file_missing_file(self, caplog) -> None:
        missing_config_file = "NOT-A-FILE.HONESTLY"
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                BasicConfig._load_yaml_file(self.mocked_obj, missing_config_file)
        assert len(caplog.text) > 0

    def test_load_exception_file_good(self) -> None:
        mocked_obj = MagicMock()
        mocked_obj._load_yaml_file = MagicMock(return_value=self.exceptions)
        returned_exceptions = BasicConfig._load_exception_file(
            mocked_obj, EXCEPTIONS_FILE
        )
        assert returned_exceptions == self.exceptions

    def test_load_config_file_good(self) -> None:
        self.mocked_obj._load_yaml_file = MagicMock(return_value=self.config)
        returned_config = BasicConfig._load_config_file(self.mocked_obj)
        assert returned_config == self.config

    def test_load_config_file_empty(self, caplog) -> None:
        self.mocked_obj._load_yaml_file = MagicMock(return_value=self.empty_config)
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                BasicConfig._load_config_file(self.mocked_obj)
        assert len(caplog.text) > 0

    def test_load_country_control_file_good(self) -> None:
        self.mocked_obj._load_yaml_file = MagicMock(return_value=self.country_control)
        returned_country_control = BasicConfig._load_country_control_file(
            self.mocked_obj, COUNTRY_CONTROL_FILE
        )
        assert returned_country_control == self.country_control

    def test_init(self) -> None:
        BasicConfig.__init__(self.mocked_obj, self.args)
        assert self.mocked_obj.args.console_log_level == self.args.console_log_level
