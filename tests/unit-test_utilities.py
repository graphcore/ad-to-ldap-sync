# type: ignore
import os
import pathlib
import pytest
import yaml
import src.utils.utilities as Utilities
import logging
from loguru import logger
from unittest.mock import MagicMock, patch
from _pytest.logging import caplog as _caplog  # noqa

CONFIG_FILE = "tests/data/test_config.yaml"
EXCEPTIONS_FILE = "tests/data/test_exceptions.yaml"
COUNTRY_CONTROL_FILE = "tests/data/test_country_control.yaml"
COUNTRY_CONTROL_FILE_EMPTY = "tests/data/test_country_control_empty.yaml"
ALL_TEST_USERS_FILE = "tests/data/all_test_users.yaml"


@pytest.fixture
def caplog(_caplog):  # noqa
    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message} {extra}")
    yield _caplog
    logger.remove(handler_id)


class TestUtilities:
    @classmethod
    def setup_class(self):
        self.args = MagicMock()
        self.basic_config = {}
        self.config = yaml.safe_load(open(CONFIG_FILE, "r"))
        self.exceptions = yaml.safe_load(open(EXCEPTIONS_FILE, "r"))
        self.country_control = yaml.safe_load(open(COUNTRY_CONTROL_FILE, "r"))
        self.country_control_empty = yaml.safe_load(
            open(COUNTRY_CONTROL_FILE_EMPTY, "r")
        )
        self.all_test_users = yaml.safe_load(open(ALL_TEST_USERS_FILE, "r"))
        openldap_connection = MagicMock()
        ad_connection = MagicMock()
        self.ldap_connections = {"ad": ad_connection, "openldap": openldap_connection}

    def setup_method(self):
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

    @staticmethod
    def remove_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def assert_is_file(path):
        if not pathlib.Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))

    def test_fill_array_gaps_1(self) -> None:
        # Normal test, single gap
        numbers = [202, 190, 201, 204, 200]
        offset = 200
        returned_value = Utilities.fill_array_gaps(numbers, offset)
        expected_value = 203
        assert returned_value == expected_value

    def test_fill_array_gaps_2(self) -> None:
        # Test when there are no gaps above the offset
        numbers = [202, 190, 201, 203, 200]
        offset = 200
        returned_value = Utilities.fill_array_gaps(numbers, offset)
        expected_value = 204
        assert returned_value == expected_value

    def test_fill_array_gaps_3(self) -> None:
        # Test if the first number of the offset is available
        numbers = [202, 190, 201]
        offset = 200
        returned_value = Utilities.fill_array_gaps(numbers, offset)
        expected_value = 200
        assert returned_value == expected_value

    def test_fill_array_gaps_4(self) -> None:
        # Test if the there are no numbers in the array that is above the offset
        numbers = [198, 190, 50]
        offset = 200
        returned_value = Utilities.fill_array_gaps(numbers, offset)
        expected_value = 200
        assert returned_value == expected_value

    def test_fill_array_gaps_5(self) -> None:
        # Test with larger gaps than 1
        numbers = [202, 190, 201, 205, 200]
        offset = 200
        returned_value = Utilities.fill_array_gaps(numbers, offset)
        expected_value = 203
        assert returned_value == expected_value

    def test_write_monitoring_log_good(self) -> None:
        Utilities.write_monitoring_log(self.basic_config, True, self.args.op_type)
        log_path = pathlib.Path(
            f"{self.args.op_type}_"
            f"{self.basic_config['config']['settings']['monitoring_log_file']}"
        )
        self.assert_is_file(log_path)
        self.remove_file(log_path)

    def test_write_monitoring_log_bad(self, caplog) -> None:
        bad_log_file = "tests/data/test_bad_config_log_file.yaml"
        bad_config_log_file = yaml.safe_load(open(bad_log_file, "r"))
        basic_config_log_file = {
            "config": bad_config_log_file,
            "exceptions": self.exceptions,
            "country_control": self.country_control_empty,
            "args": self.args,
        }
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                Utilities.write_monitoring_log(
                    basic_config_log_file, False, "some_runner"
                )
        assert len(caplog.text) > 0

    def test_user_exception_lookup(self) -> None:
        """
        The user 'test.user1' is used to test:
        1. User exists in exception lookup.
        2. Exception lookup is not equal to 'NONE'.
        3. User exists in MS AD.
        4. User does not exist in OpenLDAP.
            Therefore we need to make an empty dictionary for
            'exception', so we can copy the MS AD entry from the
            exception key entry in 'all_users'
        5. Delete the original user as it is unwanted.

        The user 'jeffr' is used to test:
        1. User exists in exception lookup.
        2. Exception lookup is equal to 'NONE'.
        3. Set the 'uid' in 'ad' to 'NONE'

        The user 'adam.addar' is used to test:
        1. User exists in exception lookup.
        2. Exception lookup is not equal to 'NONE'.
        3. The exception (in this case 'adama') exists in 'all_users'.
        4. The exception has an OpenLDAP entry.
        5. Check that for the exception lookup, both an "ad" and "openldap" key exist
           in the all_users dictionary, for the user
        """
        expected_users = yaml.safe_load(
            open("tests/data/test_users_with_exceptions.yaml", "r")
        )
        Utilities.user_exception_lookup(self.basic_config, self.all_test_users)
        assert self.all_test_users == expected_users

    def test_get_next_gid_uid_number_group(self, caplog) -> None:
        test_data = [
            {
                "attributes": {"gidNumber": "badtext"},
            },
            {
                "attributes": {"gidNumber": 1501},
            },
        ]
        local_openldap_connection = MagicMock()
        local_openldap_connection.response = test_data
        ldap_connections = {"ad": MagicMock(), "openldap": local_openldap_connection}
        with caplog.at_level(logging.WARNING):
            with patch(
                "src.utils.utilities.fill_array_gaps",
                return_value=2011,
            ):
                returned_value = Utilities.get_next_gid_uid_number(
                    self.basic_config, ldap_connections, "openldap", "group"
                )
                assert returned_value == 2011
        assert "badtext" in caplog.text

    def test_get_next_gid_uid_number_user(self, caplog) -> None:
        test_data = [
            {
                "attributes": {"uidNumber": "badtext"},
            },
            {
                "attributes": {"uidNumber": 1501},
            },
        ]
        local_openldap_connection = MagicMock()
        local_openldap_connection.response = test_data
        ldap_connections = {"ad": MagicMock(), "openldap": local_openldap_connection}
        with caplog.at_level(logging.WARNING):
            with patch(
                "src.utils.utilities.fill_array_gaps",
                return_value=2011,
            ):
                returned_value = Utilities.get_next_gid_uid_number(
                    self.basic_config, ldap_connections, "openldap", "user"
                )
                assert returned_value == 2011
        assert "badtext" in caplog.text
