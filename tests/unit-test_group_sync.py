# type: ignore
import logging
import yaml
import os
import pytest
from loguru import logger
from ldap3 import MODIFY_DELETE, MODIFY_ADD
from src.runners.group_sync import AdLdapGroupSync
from unittest.mock import MagicMock, patch
from _pytest.logging import caplog as _caplog  # noqa

CONFIG_FILE = "tests/data/test_config.yaml"
EXCEPTIONS_FILE = "tests/data/test_exceptions.yaml"
COUNTRY_CONTROL_FILE = "tests/data/test_country_control.yaml"
COUNTRY_CONTROL_FILE_EMPTY = "tests/data/test_country_control_empty.yaml"
BAD_CONFIG_FILE = "tests/data/test_bad_config.yaml"
EMPTY_CONFIG_FILE = "tests/data/test_config_empty.yaml"


@pytest.fixture
def caplog(_caplog):  # noqa
    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message} {extra}")
    yield _caplog
    logger.remove(handler_id)


class TestGroupSync:
    @classmethod
    def setup_class(self):
        self.args = MagicMock()
        self.basic_config = {}
        self.bad_config = yaml.safe_load(open(BAD_CONFIG_FILE, "r"))
        self.config = yaml.safe_load(open(CONFIG_FILE, "r"))
        self.empty_config = yaml.safe_load(open(EMPTY_CONFIG_FILE, "r"))
        self.exceptions = yaml.safe_load(open(EXCEPTIONS_FILE, "r"))
        self.country_control = yaml.safe_load(open(COUNTRY_CONTROL_FILE, "r"))
        self.country_control_empty = yaml.safe_load(
            open(COUNTRY_CONTROL_FILE_EMPTY, "r")
        )

    @staticmethod
    def remove_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def setup_method(self):
        self.mocked_obj = MagicMock()
        self.mocked_openldap_connection = MagicMock()
        self.mocked_ad_connection = MagicMock()
        self.ldap_connections = {
            "ad": self.mocked_ad_connection,
            "openldap": self.mocked_openldap_connection,
        }
        self.mocked_obj.ldap_connections = self.ldap_connections
        self.args.console_log_level = "INFO"
        self.args.config_file = CONFIG_FILE
        self.args.exception_file = EXCEPTIONS_FILE
        self.args.country_control_file = COUNTRY_CONTROL_FILE
        self.args.op_type = "unit-test-group-sync"
        self.args.environment = "noop"
        self.basic_config = {
            "config": self.config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }
        self.mocked_obj.basic_config = self.basic_config

    def teardown_method(self):
        self.remove_file("group_sync_test_monitoring.log")

    def test_main_called(self) -> None:
        mocked_obj = MagicMock()
        mocked_obj._main = MagicMock()
        AdLdapGroupSync.__init__(mocked_obj, self.basic_config, self.ldap_connections)
        assert mocked_obj._main.called

    def test_main_good_connection(self, caplog) -> None:
        with patch(
            "utils.utilities.write_monitoring_log"
        ) as mocked_write_monitoring_log:
            AdLdapGroupSync._main(self.mocked_obj)
            assert mocked_write_monitoring_log.called
        assert self.mocked_obj._build_sync_group_list.called
        assert self.mocked_obj._generate_group_operations.called
        assert self.mocked_obj._process_operations.called

    def test_group_search_good(self) -> None:
        mocked_connection = MagicMock()
        mocked_connection.result = {"result": 0}
        mocked_connection.response = "openldap_connection_data"
        returned_results = AdLdapGroupSync._group_search(
            self.mocked_obj, mocked_connection, "base string", "search string"
        )
        assert returned_results == "openldap_connection_data"

    def test_group_search_error(self) -> None:
        mocked_connection = MagicMock()
        mocked_connection.response = "openldap_connection_data"
        with patch(
            "utils.utilities.write_monitoring_log"
        ) as mocked_write_monitoring_log:
            with pytest.raises(SystemExit):
                AdLdapGroupSync._group_search(
                    self.mocked_obj, mocked_connection, "base string", "search string"
                )
            assert mocked_write_monitoring_log.called

    def test_user_search(self) -> None:
        self.mocked_obj.ldap_connections["openldap"].response = "some_user_data"
        user_dn = "bob"
        returned_results = AdLdapGroupSync._user_search(
            self.mocked_obj, "openldap", user_dn
        )
        assert returned_results == "some_user_data"

    def test_determine_user_base_default(self) -> None:
        returned_results = AdLdapGroupSync._determine_user_base(self.config, "openldap")
        assert returned_results == "ou=People,dc=example,dc=com"

    def test_determine_user_base_custom_input(self) -> None:
        returned_results = AdLdapGroupSync._determine_user_base(
            self.config, "openldap", "some_user_base"
        )
        assert returned_results == "some_user_base"

    def test_modify_group_case_1(self) -> None:
        """Check that we try to modify the group."""
        self.mocked_obj.run_status = True
        mocked_connection = MagicMock()
        mocked_connection.modify = MagicMock()
        mocked_connection.result = {"result": 0}
        AdLdapGroupSync._modify_group(
            self.mocked_obj,
            "openldap",
            mocked_connection,
            "cn=ad-ldap-sync-test,ou=Group,dc=example,dc=com",
            "some_action",
            ["some", "user", "list"],
        )
        assert mocked_connection.modify.called
        assert self.mocked_obj.run_status is True

    def test_modify_group_case_2(self, caplog) -> None:
        """No users thus no modify."""
        mocked_connection = MagicMock()
        mocked_connection.modify = MagicMock()
        with caplog.at_level(logging.DEBUG):
            AdLdapGroupSync._modify_group(
                self.mocked_obj,
                "openldap",
                mocked_connection,
                "cn=ad-ldap-sync-test,ou=Group,dc=example,dc=com",
                "some_action",
                [],
            )
        assert len(caplog.text) > 0
        assert not mocked_connection.modify.called

    def test_modify_group_case_3(self, caplog) -> None:
        """Check that we fail on error and log correctly."""
        self.mocked_obj.run_status = True
        mocked_connection = MagicMock()
        mocked_connection.result = {"result": 1}
        with caplog.at_level(logging.ERROR):
            AdLdapGroupSync._modify_group(
                self.mocked_obj,
                "openldap",
                mocked_connection,
                "cn=ad-ldap-sync-test,ou=Group,dc=example,dc=com",
                "some_action",
                ["some", "user", "list"],
            )
        assert self.mocked_obj.run_status is False
        assert len(caplog.text) > 0

    def test_determine_group_name_string(self) -> None:
        group_name_object = "bob"
        returned_group_name = AdLdapGroupSync._determine_group_name(group_name_object)
        assert returned_group_name == "bob"

    def test_determine_group_name_list(self) -> None:
        group_name_object = ["bob"]
        returned_group_name = AdLdapGroupSync._determine_group_name(group_name_object)
        assert returned_group_name == "bob"

    def test_determine_group_id_good(self) -> None:
        group = {
            "attributes": {
                "gidNumber": 25010,
            },
        }
        group_name = "bla"
        returned_group_id = AdLdapGroupSync._determine_group_id(
            self.mocked_obj, "openldap", group, group_name
        )
        assert returned_group_id == 25010

    def test_determine_group_id_bad(self) -> None:
        group = {"attributes": "bla"}
        group_name = "bla"
        returned_group_id = AdLdapGroupSync._determine_group_id(
            self.mocked_obj, "openldap", group, group_name
        )
        assert returned_group_id == -1

    def test_determine_group_members_populated(self) -> None:
        group = {
            "attributes": {
                "objectClass": ["top", "group"],
                "cn": "some_groun",
                "memberUid": [
                    "John",
                    "Jane",
                ],
            },
        }
        returned_group_members = AdLdapGroupSync._determine_group_members(
            self.mocked_obj, "openldap", group
        )
        assert returned_group_members == ["John", "Jane"]

    def test_determine_group_members_empty(self) -> None:
        group = {
            "attributes": {
                "objectClass": ["top", "group"],
                "cn": "some_groun",
            },
        }
        returned_group_members = AdLdapGroupSync._determine_group_members(
            self.mocked_obj, "openldap", group
        )
        assert returned_group_members == []

    def test_create_group_dictionary_ad(self) -> None:
        self.mocked_obj._determine_group_name = MagicMock(return_value="some_group")
        self.mocked_obj._determine_group_id = MagicMock(return_value=234567)
        self.mocked_obj._determine_group_members = MagicMock(
            return_value=["John", "Jane"]
        )
        self.mocked_obj._flatten_nested_group = MagicMock(return_value=["John", "Jane"])
        search_results = [
            {
                "dn": "some_dn",
                "attributes": {
                    "cn": "some_group",
                    "member": [
                        "CN=John Doe,OU=Users,OU=User Accounts,DC=example,DC=com",
                    ],
                    "name": "some_group",
                    "sAMAccountName": "some_Group",
                    "gidNumber": 234567,
                },
            }
        ]
        returned_group = AdLdapGroupSync._create_group_dictionary(
            self.mocked_obj,
            "ad",
            search_results,
        )
        assert returned_group == {
            "some_group": {
                "dn": "some_dn",
                "id": 234567,
                "names": ["John", "Jane"],
                "server_type": "ad",
            }
        }

    def test_create_group_dictionary_openldap(self) -> None:
        self.mocked_obj._determine_group_name = MagicMock(return_value="some_group")
        self.mocked_obj._determine_group_id = MagicMock(return_value=234567)
        self.mocked_obj._determine_group_members = MagicMock(
            return_value=["John", "Jane"]
        )
        search_results = [
            {
                "dn": "some_dn",
                "attributes": {
                    "cn": "some_group",
                    "member": [
                        "CN=John Doe,OU=Users,OU=User Accounts,DC=example,DC=com",
                    ],
                    "name": "some_group",
                    "sAMAccountName": "some_Group",
                    "gidNumber": 234567,
                },
            }
        ]
        returned_group = AdLdapGroupSync._create_group_dictionary(
            self.mocked_obj,
            "openldap",
            search_results,
        )
        assert returned_group == {
            "some_group": {
                "dn": "some_dn",
                "id": 234567,
                "names": ["John", "Jane"],
                "server_type": "openldap",
            }
        }

    def test_build_sync_group_list_valid(self, caplog) -> None:
        first_group_dict = {"test-group": {"id": 234567}}
        second_group_dict = {"test-group": {"id": 234567}}
        with caplog.at_level(logging.INFO):
            returned_group_list = AdLdapGroupSync._build_sync_group_list(
                first_group_dict, second_group_dict
            )
        assert returned_group_list == ["test-group"]
        assert len(caplog.text) > 0

    def test_build_sync_group_list_mismatch(self, caplog) -> None:
        first_group_dict = {"test-group": {"id": 111111}}
        second_group_dict = {"test-group": {"id": 999999}}
        with caplog.at_level(logging.DEBUG):
            returned_group_list = AdLdapGroupSync._build_sync_group_list(
                first_group_dict, second_group_dict
            )
        assert returned_group_list == []
        assert len(caplog.text) > 0

    def test_build_sync_group_list_only_one_directory(self, caplog) -> None:
        first_group_dict = {"test-group": {"id": 234567}}
        second_group_dict = {}
        with caplog.at_level(logging.DEBUG):
            returned_group_list = AdLdapGroupSync._build_sync_group_list(
                first_group_dict, second_group_dict
            )
        assert returned_group_list == []
        assert len(caplog.text) > 0

    def test_check_country_control_no_control(self) -> None:
        # If there is no country control data, we don't do any restrictions.
        account_data = {}
        valid_sync_group = ""
        self.basic_config_empty = {
            "config": self.config,
            "exceptions": self.exceptions,
            "country_control": self.country_control_empty,
            "args": self.args,
        }
        returned_value = AdLdapGroupSync._check_country_control(
            self.mocked_obj, account_data, valid_sync_group
        )
        assert returned_value is True

    def test_check_country_control_not_in_controlled(self) -> None:
        # If the group is not in the contry control data, we don't restrict.
        account_data = {
            "sAMAccountName": "bob",
            "country_code": "TW",
        }
        valid_sync_group = "not-controlled-group"
        returned_value = AdLdapGroupSync._check_country_control(
            self.mocked_obj, account_data, valid_sync_group
        )
        assert returned_value is True

    def test_check_country_control_user_not_allow(self, caplog) -> None:
        # If the account does not have country code (like service accounts),
        # we don't restrict.
        account_data = {
            "sAMAccountName": "service_account",
            "country_code": "",
        }
        valid_sync_group = "ad-ldap-sync-test"
        with caplog.at_level(logging.DEBUG):
            returned_value = AdLdapGroupSync._check_country_control(
                self.mocked_obj, account_data, valid_sync_group
            )
        assert returned_value is True

    def test_check_country_control_user_allow(self, caplog) -> None:
        # If the user's country code is in the controlled list for this group, allow.
        account_data = {
            "sAMAccountName": "Test User",
            "country_code": "GB",
        }
        valid_sync_group = "ad-ldap-sync-test"
        returned_value = AdLdapGroupSync._check_country_control(
            self.mocked_obj, account_data, valid_sync_group
        )
        assert returned_value is True

    def test_check_country_control_user_deny(self, caplog) -> None:
        # If the user's country code is not in the controlled list for this group:
        #  Deny and notify via logging
        account_data = {
            "sAMAccountName": "Test User",
            "country_code": "XX",
        }
        valid_sync_group = "ad-ldap-sync-test"
        with caplog.at_level(logging.DEBUG):
            returned_value = AdLdapGroupSync._check_country_control(
                self.mocked_obj, account_data, valid_sync_group
            )
        assert len(caplog.text) > 0
        assert returned_value is False

    def test_determine_change_percent_devide_by_zero(self) -> None:
        destination_list = []
        destination_operations = {
            "deletions": ["user_a", "user_b", "user_c"],
            "additions": [
                "user_m",
                "user_n",
                "user_o",
                "user_p",
                "user_q",
            ],
        }
        returned_change_data = AdLdapGroupSync._determine_change_percent(
            destination_list, destination_operations
        )
        assert returned_change_data == {
            "deletions_len": 3,
            "additions_len": 5,
            "original_len": 1,
            "total_change_percent": 800,
            "deletions_change_percent": 300,
            "additions_change_percent": 500,
            "total_change_size": 8,
        }

    def test_determine_change_percent_normal(self) -> None:
        destination_list = ["john", "jane", "doe"]
        destination_operations = {
            "deletions": ["user_a", "user_b", "user_c"],
            "additions": [
                "user_m",
                "user_n",
                "user_o",
                "user_p",
                "user_q",
            ],
        }
        returned_change_data = AdLdapGroupSync._determine_change_percent(
            destination_list, destination_operations
        )
        assert returned_change_data == {
            "deletions_len": 3,
            "original_len": 3,
            "additions_len": 5,
            "total_change_percent": 266,
            "deletions_change_percent": 100,
            "additions_change_percent": 166,
            "total_change_size": 8,
        }

    def test_check_override_required_case_1(self, caplog) -> None:
        """No overrides."""
        change_data = {
            "original_len": 1,
            "deletions_len": 1,
            "additions_len": 1,
            "total_change_percent": 40,
            "deletions_change_percent": 20,
            "additions_change_percent": 20,
            "total_change_size": 2,
        }
        self.mocked_obj._determine_change_percent = MagicMock(return_value=change_data)
        destination_list = ["user_a", "user_b", "user_c", "user_d", "user_e"]
        destination_operations = {"deletions": ["jane"], "additions": ["john"]}
        group_name = "test group"
        with caplog.at_level(logging.DEBUG):
            returned_override_required = AdLdapGroupSync._check_override_required(
                self.mocked_obj,
                destination_list,
                destination_operations,
                group_name,
            )
        assert group_name in caplog.text
        assert str(change_data["total_change_size"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(change_data["original_len"]) in caplog.text
        assert str(change_data["additions_len"]) in caplog.text
        assert str(change_data["additions_change_percent"]) in caplog.text
        assert str(change_data["deletions_len"]) in caplog.text
        assert str(change_data["deletions_change_percent"]) in caplog.text
        assert returned_override_required is False

    def test_check_override_required_case_2(self, caplog) -> None:
        """Total change override required."""
        self.mocked_obj.basic_config["config"]["settings"][
            "small_group_blind_update"
        ] = 0
        change_data = {
            "original_len": 1,
            "deletions_len": 1,
            "additions_len": 4,
            "total_change_percent": 100,
            "deletions_change_percent": 20,
            "additions_change_percent": 20,
            "total_change_size": 5,
        }
        self.mocked_obj._determine_change_percent = MagicMock(return_value=change_data)
        destination_list = ["user_a", "user_b", "user_c", "user_d", "user_e"]
        destination_operations = {
            "deletions": ["user_a"],
            "additions": ["user_1", "user_2", "user_3", "user_4"],
        }
        group_name = "test group"
        with caplog.at_level(logging.DEBUG):
            returned_override_required = AdLdapGroupSync._check_override_required(
                self.mocked_obj,
                destination_list,
                destination_operations,
                group_name,
            )
        assert group_name in caplog.text
        assert str(change_data["total_change_size"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(change_data["original_len"]) in caplog.text
        assert str(change_data["additions_len"]) in caplog.text
        assert str(change_data["additions_change_percent"]) in caplog.text
        assert str(change_data["deletions_len"]) in caplog.text
        assert str(change_data["deletions_change_percent"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(self.config["settings"]["total_change_threshold"]) in caplog.text
        assert returned_override_required is True

    def test_check_override_required_case_3(self, caplog) -> None:
        """Deletion change override required."""
        self.mocked_obj.basic_config["config"]["settings"][
            "small_group_blind_update"
        ] = 0
        change_data = {
            "original_len": 1,
            "deletions_len": 4,
            "additions_len": 0,
            "total_change_percent": 44,
            "deletions_change_percent": 44,
            "additions_change_percent": 0,
            "total_change_size": 4,
        }
        self.mocked_obj._determine_change_percent = MagicMock(return_value=change_data)
        destination_list = [
            "user_a",
            "user_b",
            "user_c",
            "user_d",
            "user_e",
            "user_f",
            "user_g",
            "user_h",
            "user_i",
        ]
        destination_operations = {
            "deletions": ["user_a", "user_b", "user_c", "user_d"],
            "additions": [],
        }
        group_name = "test group"
        with caplog.at_level(logging.DEBUG):
            returned_override_required = AdLdapGroupSync._check_override_required(
                self.mocked_obj,
                destination_list,
                destination_operations,
                group_name,
            )
        assert group_name in caplog.text
        assert str(change_data["total_change_size"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(change_data["original_len"]) in caplog.text
        assert str(change_data["additions_len"]) in caplog.text
        assert str(change_data["additions_change_percent"]) in caplog.text
        assert str(change_data["deletions_len"]) in caplog.text
        assert str(change_data["deletions_change_percent"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(self.config["settings"]["deletions_change_threshold"]) in caplog.text
        assert returned_override_required is True

    def test_check_override_required_case_4(self, caplog) -> None:
        """Addition change override required."""
        self.mocked_obj.basic_config["config"]["settings"][
            "small_group_blind_update"
        ] = 0
        change_data = {
            "original_len": 1,
            "deletions_len": 0,
            "additions_len": 4,
            "total_change_percent": 44,
            "deletions_change_percent": 0,
            "additions_change_percent": 44,
            "total_change_size": 4,
        }
        self.mocked_obj._determine_change_percent = MagicMock(return_value=change_data)
        destination_list = [
            "user_a",
            "user_b",
            "user_c",
            "user_d",
            "user_e",
            "user_f",
            "user_g",
            "user_h",
            "user_i",
        ]
        destination_operations = {
            "deletions": [],
            "additions": ["user_j", "user_k", "user_l", "user_m"],
        }
        group_name = "test group"
        with caplog.at_level(logging.DEBUG):
            returned_override_required = AdLdapGroupSync._check_override_required(
                self.mocked_obj,
                destination_list,
                destination_operations,
                group_name,
            )
        assert group_name in caplog.text
        assert str(change_data["total_change_size"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(change_data["original_len"]) in caplog.text
        assert str(change_data["additions_len"]) in caplog.text
        assert str(change_data["additions_change_percent"]) in caplog.text
        assert str(change_data["deletions_len"]) in caplog.text
        assert str(change_data["deletions_change_percent"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(self.config["settings"]["additions_change_threshold"]) in caplog.text
        assert returned_override_required is True

    def test_check_override_required_case_5(self, caplog) -> None:
        """Small group blind update."""
        self.mocked_obj.basic_config["config"]["settings"][
            "small_group_blind_update"
        ] = 10
        change_data = {
            "original_len": 1,
            "deletions_len": 0,
            "additions_len": 4,
            "total_change_percent": 44,
            "deletions_change_percent": 0,
            "additions_change_percent": 44,
            "total_change_size": 4,
        }
        self.mocked_obj._determine_change_percent = MagicMock(return_value=change_data)
        destination_list = [
            "user_a",
            "user_b",
            "user_c",
            "user_d",
            "user_e",
            "user_f",
            "user_g",
            "user_h",
            "user_i",
        ]
        destination_operations = {
            "deletions": [],
            "additions": ["user_j", "user_k", "user_l", "user_m"],
        }
        group_name = "test group"
        with caplog.at_level(logging.DEBUG):
            returned_override_required = AdLdapGroupSync._check_override_required(
                self.mocked_obj,
                destination_list,
                destination_operations,
                group_name,
            )
        assert group_name in caplog.text
        assert str(change_data["total_change_size"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(change_data["original_len"]) in caplog.text
        assert str(change_data["additions_len"]) in caplog.text
        assert str(change_data["additions_change_percent"]) in caplog.text
        assert str(change_data["deletions_len"]) in caplog.text
        assert str(change_data["deletions_change_percent"]) in caplog.text
        assert str(change_data["total_change_percent"]) in caplog.text
        assert str(self.config["settings"]["additions_change_threshold"]) in caplog.text
        assert str(self.config["settings"]["small_group_blind_update"]) in caplog.text
        assert returned_override_required is False

    def test_get_account_data_no_ad_user(self, caplog) -> None:
        self.mocked_obj._user_search = MagicMock(side_effect=Exception("exc output"))
        ad_user = "CN=John Doe,OU=Users,OU=User Accounts,DC=example,DC=com"
        with caplog.at_level(logging.WARNING):
            returned_account_data = AdLdapGroupSync._get_account_data(
                self.mocked_obj, ad_user
            )

        assert "John Doe" in caplog.text
        assert returned_account_data == {
            "account_active": False,
            "sAMAccountName": "",
            "country_code": None,
        }

    def test_get_account_data_good(self) -> None:
        mocked_obj = MagicMock()
        mocked_obj.basic_config = self.basic_config
        full_output = [
            {
                "attributes": {
                    "c": "GB",
                    "sAMAccountName": "JohnD",
                    "userAccountControl": 10,
                }
            }
        ]
        mocked_obj._user_search = MagicMock(return_value=full_output)
        ad_user = "CN=John Doe,OU=Users,OU=User Accounts,DC=example,DC=com"
        returned_account_data = AdLdapGroupSync._get_account_data(mocked_obj, ad_user)
        assert returned_account_data == {
            "account_active": True,
            "sAMAccountName": "johnd",
            "country_code": "GB",
        }

    def test_find_user_in_destination_dict_true(self) -> None:
        account_data = {"sAMAccountName": "johnd", "account_active": True}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users,OU=Grap"],
            }
        }
        returned_found = AdLdapGroupSync._find_user_in_source_dict(
            self.mocked_obj,
            source_dict,
            "johnd",
            "test_group",
        )
        assert returned_found is True

    def test_find_user_in_destination_dict_false(self) -> None:
        account_data = {"sAMAccountName": "johnd", "account_active": True}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users,OU=Grap"],
            }
        }
        returned_found = AdLdapGroupSync._find_user_in_source_dict(
            self.mocked_obj,
            source_dict,
            "bob",
            "test_group",
        )
        assert returned_found is False

    def test_generate_additions_case_1(self) -> None:
        # User not in destination dict - aka new user
        # 'sAMAccountName' not empty
        # User account is active
        # User not restricted by country control
        # This is the only case that we add a user
        self.mocked_obj._check_country_control = MagicMock(return_value=True)
        account_data = {"sAMAccountName": "johnd", "account_active": True}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users"],
            }
        }
        destination_dict = {"test_group": {"names": ["user_a"]}}
        returned_additions = AdLdapGroupSync._generate_additions(
            self.mocked_obj,
            source_dict,
            destination_dict,
            "test_group",
        )
        assert returned_additions == ["johnd"]

    def test_generate_additions_case_2(self) -> None:
        # User not in destination dict - aka new user
        # 'sAMAccountName' not empty
        # User account is active
        # User is restricted by country control - DO NOT ADD
        self.mocked_obj._check_country_control = MagicMock(return_value=False)
        account_data = {"sAMAccountName": "johnd", "account_active": True}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users"],
            }
        }
        destination_dict = {"test_group": {"names": ["user_a"]}}
        returned_additions = AdLdapGroupSync._generate_additions(
            self.mocked_obj,
            source_dict,
            destination_dict,
            "test_group",
        )
        assert returned_additions == []

    def test_generate_additions_case_3(self) -> None:
        # User not in destination dict - aka new user
        # 'sAMAccountName' not empty
        # User account is inactive - DO NOT ADD
        # User not restricted by country control
        self.mocked_obj._check_country_control = MagicMock(return_value=True)
        account_data = {"sAMAccountName": "johnd", "account_active": False}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users"],
            }
        }
        destination_dict = {"test_group": {"names": ["user_a"]}}
        returned_additions = AdLdapGroupSync._generate_additions(
            self.mocked_obj,
            source_dict,
            destination_dict,
            "test_group",
        )
        assert returned_additions == []

    def test_generate_additions_case_4(self) -> None:
        # User not in destination dict - aka new user
        # 'sAMAccountName' empty - DO NOT ADD
        # User account is active
        # User not restricted by country control
        self.mocked_obj._check_country_control = MagicMock(return_value=True)
        account_data = {"sAMAccountName": "", "account_active": True}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users"],
            }
        }
        destination_dict = {"test_group": {"names": ["user_a"]}}
        returned_additions = AdLdapGroupSync._generate_additions(
            self.mocked_obj,
            source_dict,
            destination_dict,
            "test_group",
        )
        assert returned_additions == []

    def test_generate_additions_case_5(self) -> None:
        # User is in destination dict - DO NOT ADD
        # 'sAMAccountName' not empty
        # User account is active
        # User not restricted by country control
        self.mocked_obj._check_country_control = MagicMock(return_value=True)
        account_data = {"sAMAccountName": "johnd", "account_active": True}
        self.mocked_obj._lookup_ad_user = MagicMock(return_value=account_data)
        source_dict = {
            "test_group": {
                "id": 234567,
                "names": ["CN=John Doe,OU=Users"],
            }
        }
        destination_dict = {"test_group": {"names": ["user_a", "johnd"]}}
        returned_additions = AdLdapGroupSync._generate_additions(
            self.mocked_obj,
            source_dict,
            destination_dict,
            "test_group",
        )
        assert returned_additions == []

    def test_generate_deletions_no_deletes(self) -> None:
        self.mocked_obj._find_user_in_destination_dict = MagicMock(return_value=True)
        source_dict = {}
        destination_dict = {"test_group": {"names": ["user_a", "johnd"]}}
        valid_sync_group = "test_group"
        returned_deletions = AdLdapGroupSync._generate_deletions(
            self.mocked_obj,
            destination_dict,
            source_dict,
            valid_sync_group,
        )
        assert returned_deletions == []

    def test_generate_deletions_delete_user(self) -> None:
        self.mocked_obj._find_user_in_source_dict = MagicMock(return_value=False)
        source_dict = {}
        destination_dict = {"test_group": {"names": ["johnd"]}}
        valid_sync_group = "test_group"
        returned_deletions = AdLdapGroupSync._generate_deletions(
            self.mocked_obj,
            destination_dict,
            source_dict,
            valid_sync_group,
        )
        assert returned_deletions == ["johnd"]

    def test_generate_group_operations(self) -> None:
        self.mocked_obj._check_override_required = MagicMock(return_value=False)
        self.mocked_obj._generate_additions = MagicMock(return_value=[])
        self.mocked_obj._generate_deletions = MagicMock(return_value=["johnd"])
        source_dict = {}
        destination_dict = {"test_group_1": {"names": ""}}
        valid_sync_groups = ["test_group_1"]
        returned_destination_operations = AdLdapGroupSync._generate_group_operations(
            self.mocked_obj,
            source_dict,
            destination_dict,
            valid_sync_groups,
        )
        assert returned_destination_operations == {
            "test_group_1": {
                "additions": [],
                "deletions": ["johnd"],
                "override_required": False,
            }
        }

    def test_lookup_ad_user_case_1(self) -> None:
        # User is in cache
        self.mocked_obj.user_lookup_cache = {
            "CN=John Doe,OU=Users": {
                "sAMAccountName": "johnd",
                "country_code": "GB",
                "account_active": True,
            }
        }
        ad_user = "CN=John Doe,OU=Users"
        returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "johnd",
            "country_code": "GB",
            "account_active": True,
        }

    def test_lookup_ad_user_case_2(self) -> None:
        # User is in cache
        # Check that we handle empty exceptions data
        self.mocked_obj.user_lookup_cache = {
            "CN=John Doe,OU=Users": {
                "sAMAccountName": "johnd",
                "country_code": "GB",
                "account_active": True,
            }
        }
        ad_user = "CN=John Doe,OU=Users"
        empty_exceptions = {}
        local_basic_config = {
            "config": self.config,
            "exceptions": empty_exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }
        self.mocked_obj.basic_config = local_basic_config
        returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "johnd",
            "country_code": "GB",
            "account_active": True,
        }

    def test_lookup_ad_user_case_3(self) -> None:
        # User is not in cache
        # Exceptions is not empty
        # Account is in exceptions (see data file)
        #  Searching in OpenLDAP for this exception yielded 1 result
        self.mocked_obj.user_lookup_cache = {}
        exception_lookup = ["johnd"]
        self.mocked_obj._user_search = MagicMock(return_value=exception_lookup)
        local_account_data = {
            "sAMAccountName": "john.d",
            "country_code": "GB",
            "account_active": True,
        }
        self.mocked_obj._get_account_data = MagicMock(return_value=local_account_data)
        ad_user = "CN=John Doe,OU=Users"
        returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "johnd",
            "country_code": "GB",
            "account_active": True,
        }

    def test_lookup_ad_user_case_4(self, caplog) -> None:
        # User is not in cache
        # Exceptions is not empty
        # Account is in exceptions (see data file)
        #  Searching in OpenLDAP for this exception yielded 0 results
        #  The sAMAccountName (in data file) is not NONE
        self.mocked_obj.run_status = True
        self.mocked_obj.user_lookup_cache = {}
        exception_lookup = []
        self.mocked_obj._user_search = MagicMock(return_value=exception_lookup)
        local_account_data = {
            "sAMAccountName": "tom.happy",
            "country_code": "GB",
            "account_active": True,
        }
        self.mocked_obj._get_account_data = MagicMock(return_value=local_account_data)
        ad_user = "CN=Tom Happy,OU=Users"
        with caplog.at_level(logging.WARNING):
            returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "",
            "country_code": None,
            "account_active": False,
        }
        assert local_account_data["sAMAccountName"] in caplog.text
        assert "target not in OpenLDAP" in caplog.text
        assert self.mocked_obj.run_status is False

    def test_lookup_ad_user_case_5(self) -> None:
        # User is not in cache
        # Exceptions is not empty
        # Account is in exceptions (see data file)
        #  Searching in OpenLDAP for this exception yielded 0 results
        #  The sAMAccountName (in data file) is NONE
        self.mocked_obj.user_lookup_cache = {}
        exception_lookup = []
        self.mocked_obj._user_search = MagicMock(return_value=exception_lookup)
        local_account_data = {
            "sAMAccountName": "jeffr",
            "country_code": "GB",
            "account_active": True,
        }
        self.mocked_obj._get_account_data = MagicMock(return_value=local_account_data)
        ad_user = "CN=Jeff Roe,OU=Users"
        returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "",
            "country_code": None,
            "account_active": False,
        }

    def test_lookup_ad_user_case_6(self, caplog) -> None:
        # User is not in cache
        # Exceptions is not empty
        # Account is in exceptions (see data file)
        #  Searching in OpenLDAP for this exception yielded >1 results
        self.mocked_obj.run_status = True
        self.mocked_obj.user_lookup_cache = {}
        exception_lookup = ["johnda", "johndb"]
        self.mocked_obj._user_search = MagicMock(return_value=exception_lookup)
        local_account_data = {
            "sAMAccountName": "john.d",
            "country_code": "GB",
            "account_active": True,
        }
        self.mocked_obj._get_account_data = MagicMock(return_value=local_account_data)
        ad_user = "CN=John Doe,OU=Users"
        with caplog.at_level(logging.WARNING):
            returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "",
            "country_code": None,
            "account_active": False,
        }
        assert local_account_data["sAMAccountName"] in caplog.text
        assert "matches multiple objects in OpenLDAP" in caplog.text
        assert self.mocked_obj.run_status is False

    def test_lookup_ad_user_case_7(self) -> None:
        # User is not in cache
        # Exceptions is not empty
        # Account is not in exceptions (see data file)
        #  Searching in OpenLDAP for this exception yielded 1 results
        self.mocked_obj.user_lookup_cache = {}
        ldap_lookup = ["bobd"]
        self.mocked_obj._user_search = MagicMock(return_value=ldap_lookup)
        local_account_data = {
            "sAMAccountName": "bobd",
            "country_code": "GB",
            "account_active": True,
        }
        self.mocked_obj._get_account_data = MagicMock(return_value=local_account_data)
        ad_user = "CN=John Doe,OU=Users"
        returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "bobd",
            "country_code": "GB",
            "account_active": True,
        }

    def test_lookup_ad_user_case_8(self, caplog) -> None:
        # User is not in cache
        # Exceptions is not empty
        # Account is not in exceptions (see data file)
        #  Searching in OpenLDAP for this exception yielded 0 or more than 1 results
        self.mocked_obj.user_lookup_cache = {}
        ldap_lookup = []
        self.mocked_obj._user_search = MagicMock(return_value=ldap_lookup)
        local_account_data = {
            "sAMAccountName": "bobd",
            "country_code": "GB",
            "account_active": True,
        }
        self.mocked_obj._get_account_data = MagicMock(return_value=local_account_data)
        ad_user = "CN=John Doe,OU=Users"
        with caplog.at_level(logging.WARNING):
            returned_ad_user = AdLdapGroupSync._lookup_ad_user(self.mocked_obj, ad_user)
        assert returned_ad_user == {
            "sAMAccountName": "",
            "country_code": None,
            "account_active": False,
        }
        assert "than one account found. Skipping." in caplog.text
        assert self.mocked_obj.run_status is False

    def test_process_operations_case_1(self) -> None:
        # Do not process any changes
        self.mocked_obj._check_process_changes = MagicMock(return_value=False)
        self.mocked_obj._modify_group = MagicMock()
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["bob"],
                "deletions": ["joe"],
                "override_required": False,
            }
        }
        AdLdapGroupSync._process_operations(
            self.mocked_obj,
            "unused",
            group_operations,
        )
        assert self.mocked_obj._modify_group.call_count == 0

    def test_process_operations_case_2(self) -> None:
        # Process all changes
        self.mocked_obj.ldap_connections = self.ldap_connections
        self.mocked_obj._check_process_changes = MagicMock(return_value=True)
        self.mocked_obj._modify_group = MagicMock()
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["bob"],
                "deletions": ["joe"],
                "override_required": False,
            }
        }
        AdLdapGroupSync._process_operations(
            self.mocked_obj,
            "unused",
            group_operations,
        )
        assert self.mocked_obj._modify_group.call_count == 2
        add_args, add_kwargs = self.mocked_obj._modify_group._mock_call_args_list[0]
        assert add_args[3] == MODIFY_ADD
        del_args, del_kwargs = self.mocked_obj._modify_group._mock_call_args_list[1]
        assert del_args[3] == MODIFY_DELETE

    def test_check_process_changes_case_1(self) -> None:
        # There are no additions or deletions
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": [],
                "deletions": [],
                "override_required": False,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {}
        process_changes = AdLdapGroupSync._check_process_changes(
            self.mocked_obj, destination_group, group, group_operations
        )
        assert process_changes is False

    def test_check_process_changes_case_2(self, caplog) -> None:
        # There are additions but no deletions
        # Override is not required
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["bob"],
                "deletions": [],
                "override_required": False,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {}
        with caplog.at_level(logging.INFO):
            process_changes = AdLdapGroupSync._check_process_changes(
                self.mocked_obj,
                destination_group,
                group,
                group_operations,
            )
        assert process_changes is True
        assert "No override required" in caplog.text

    def test_check_process_changes_case_3(self, caplog) -> None:
        # There are deletions but no additions
        # Override is not required
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": [],
                "deletions": ["bob"],
                "override_required": False,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {}
        with caplog.at_level(logging.INFO):
            process_changes = AdLdapGroupSync._check_process_changes(
                self.mocked_obj,
                destination_group,
                group,
                group_operations,
            )
        assert process_changes is True
        assert "No override required" in caplog.text

    def test_check_process_changes_case_4(self, caplog) -> None:
        # There are deletions and additions
        # Override is not required
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["jane"],
                "deletions": ["bob"],
                "override_required": False,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {}
        with caplog.at_level(logging.INFO):
            process_changes = AdLdapGroupSync._check_process_changes(
                self.mocked_obj,
                destination_group,
                group,
                group_operations,
            )
        assert process_changes is True
        assert "No override required" in caplog.text

    def test_check_process_changes_case_5(self, caplog) -> None:
        # There are deletions or additions
        # Override is required
        # Universal override is set
        self.args.universal_override = True
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["jane"],
                "deletions": ["bob"],
                "override_required": True,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {}
        with caplog.at_level(logging.INFO):
            process_changes = AdLdapGroupSync._check_process_changes(
                self.mocked_obj,
                destination_group,
                group,
                group_operations,
            )
        assert process_changes is True
        assert "Running in override" in caplog.text

    def test_check_process_changes_case_6(self, caplog) -> None:
        # There are deletions or additions
        # Override is required
        # Override for this group is set
        self.args.universal_override = False
        self.args.group_override = ["ad-ldap-sync-test"]
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["jane"],
                "deletions": ["bob"],
                "override_required": True,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {}
        with caplog.at_level(logging.INFO):
            process_changes = AdLdapGroupSync._check_process_changes(
                self.mocked_obj,
                destination_group,
                group,
                group_operations,
            )
        assert process_changes is True
        assert "Running in override" in caplog.text

    def test_check_process_changes_case_7(self, caplog) -> None:
        # There are deletions or additions
        # Override is required
        # Neither global override nor group specific override supplied
        self.args.universal_override = False
        self.args.group_override = []
        group_operations = {
            "ad-ldap-sync-test": {
                "additions": ["jane"],
                "deletions": ["bob"],
                "override_required": True,
            }
        }
        group = "ad-ldap-sync-test"
        destination_group = {"ad-ldap-sync-test": {"names": ["user_a"]}}
        with caplog.at_level(logging.WARNING):
            process_changes = AdLdapGroupSync._check_process_changes(
                self.mocked_obj,
                destination_group,
                group,
                group_operations,
            )
        assert process_changes is False
        assert "Breaches thresholds" in caplog.text
        assert "user_a" in caplog.text
        assert "jane" in caplog.text
        assert "bob" in caplog.text

    def test_new_ldap_group_case_1(self) -> None:
        # Test group with an ID that is not -1
        # Expect success
        mocked_openldap_connection = MagicMock()
        local_ldap_connections = {
            "openldap": mocked_openldap_connection,
            "ad": self.mocked_ad_connection,
        }
        self.mocked_obj.ldap_connections = local_ldap_connections
        mocked_openldap_connection.result = {"result": 0}
        openldap_group_dictionary = {}
        expected_openldap_group_dictionary = {
            "test_group": {
                "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                "id": 5,
                "server_type": "openldap",
                "names": [],
            }
        }
        ad_group_dictionary = {"test_group": {"id": 5}}
        AdLdapGroupSync._new_ldap_group(
            self.mocked_obj,
            "openldap",
            "test_group",
            openldap_group_dictionary,
            ad_group_dictionary,
        )
        assert openldap_group_dictionary == expected_openldap_group_dictionary

    def test_new_ldap_group_case_2(self, caplog) -> None:
        # Test group with an ID that is not -1
        # Expect failure on setting OpenLDAP group
        self.mocked_obj.run_status = True
        mocked_openldap_connection = MagicMock()
        local_ldap_connections = {
            "openldap": mocked_openldap_connection,
            "ad": self.mocked_ad_connection,
        }
        self.mocked_obj.ldap_connections = local_ldap_connections
        mocked_openldap_connection.result = {"result": 4}
        openldap_group_dictionary = {}
        expected_openldap_group_dictionary = {}
        ad_group_dictionary = {"test_group": {"id": 5}}
        with caplog.at_level(logging.ERROR):
            AdLdapGroupSync._new_ldap_group(
                self.mocked_obj,
                "openldap",
                "test_group",
                openldap_group_dictionary,
                ad_group_dictionary,
            )
        assert openldap_group_dictionary == expected_openldap_group_dictionary
        assert "Failed" in caplog.text
        assert self.mocked_obj.run_status is False

    def test_new_ldap_group_case_3(self) -> None:
        # Test group without an ID
        # Expect success
        mocked_openldap_connection = MagicMock()
        mocked_ad_connection = MagicMock()
        local_ldap_connections = {
            "openldap": mocked_openldap_connection,
            "ad": mocked_ad_connection,
        }
        self.mocked_obj.ldap_connections = local_ldap_connections
        mocked_openldap_connection.result = {"result": 0}
        mocked_ad_connection.result = {"result": 0}
        openldap_group_dictionary = {}
        expected_openldap_group_dictionary = {
            "test_group": {
                "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                "id": 1234,
                "server_type": "openldap",
                "names": [],
            }
        }
        ad_group_dictionary = {"test_group": {"some_attribute": "some_value"}}
        expected_ad_group_dictionary = {
            "test_group": {"some_attribute": "some_value", "id": 1234}
        }
        with patch("utils.utilities.get_next_gid_uid_number", return_value=1234):
            AdLdapGroupSync._new_ldap_group(
                self.mocked_obj,
                "openldap",
                "test_group",
                openldap_group_dictionary,
                ad_group_dictionary,
            )
        assert openldap_group_dictionary == expected_openldap_group_dictionary
        assert ad_group_dictionary == expected_ad_group_dictionary

    def test_new_ldap_group_case_4(self, caplog) -> None:
        # Test group without an ID
        # Expect failure on setting MS AD GID
        mocked_openldap_connection = MagicMock()
        mocked_ad_connection = MagicMock()
        local_ldap_connections = {
            "openldap": mocked_openldap_connection,
            "ad": mocked_ad_connection,
        }
        self.mocked_obj.ldap_connections = local_ldap_connections
        mocked_openldap_connection.result = {"result": 0}
        mocked_ad_connection.result = {"result": 4}
        openldap_group_dictionary = {}
        expected_openldap_group_dictionary = {
            "test_group": {
                "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                "id": 1234,
                "server_type": "openldap",
                "names": [],
            }
        }
        ad_group_dictionary = {"test_group": {"some_attribute": "some_value"}}
        expected_ad_group_dictionary = {"test_group": {"some_attribute": "some_value"}}
        with patch("utils.utilities.get_next_gid_uid_number", return_value=1234):
            AdLdapGroupSync._new_ldap_group(
                self.mocked_obj,
                "openldap",
                "test_group",
                openldap_group_dictionary,
                ad_group_dictionary,
            )
        assert "Failed" in caplog.text
        assert openldap_group_dictionary == expected_openldap_group_dictionary
        assert ad_group_dictionary == expected_ad_group_dictionary

    def test_new_ldap_group_case_5(self) -> None:
        # Test group with an ID -1
        # Expect success
        mocked_openldap_connection = MagicMock()
        mocked_ad_connection = MagicMock()
        local_ldap_connections = {
            "openldap": mocked_openldap_connection,
            "ad": mocked_ad_connection,
        }
        self.mocked_obj.ldap_connections = local_ldap_connections
        mocked_openldap_connection.result = {"result": 0}
        mocked_ad_connection.result = {"result": 0}
        openldap_group_dictionary = {}
        expected_openldap_group_dictionary = {
            "test_group": {
                "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                "id": 1234,
                "server_type": "openldap",
                "names": [],
            }
        }
        ad_group_dictionary = {"test_group": {"id": -1}}
        expected_ad_group_dictionary = {"test_group": {"id": 1234}}
        with patch("utils.utilities.get_next_gid_uid_number", return_value=1234):
            AdLdapGroupSync._new_ldap_group(
                self.mocked_obj,
                "openldap",
                "test_group",
                openldap_group_dictionary,
                ad_group_dictionary,
            )
        assert openldap_group_dictionary == expected_openldap_group_dictionary
        assert ad_group_dictionary == expected_ad_group_dictionary

    def test_new_ldap_group_case_6(self, caplog) -> None:
        # Test group with an ID of -1
        # Expect failure on setting MS AD GID
        mocked_openldap_connection = MagicMock()
        mocked_ad_connection = MagicMock()
        local_ldap_connections = {
            "openldap": mocked_openldap_connection,
            "ad": mocked_ad_connection,
        }
        self.mocked_obj.ldap_connections = local_ldap_connections
        mocked_openldap_connection.result = {"result": 0}
        mocked_ad_connection.result = {"result": 4}
        openldap_group_dictionary = {}
        expected_openldap_group_dictionary = {
            "test_group": {
                "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                "id": 1234,
                "server_type": "openldap",
                "names": [],
            }
        }
        ad_group_dictionary = {"test_group": {"id": -1}}
        expected_ad_group_dictionary = {"test_group": {"id": -1}}
        with patch("utils.utilities.get_next_gid_uid_number", return_value=1234):
            AdLdapGroupSync._new_ldap_group(
                self.mocked_obj,
                "openldap",
                "test_group",
                openldap_group_dictionary,
                ad_group_dictionary,
            )
        assert "Failed" in caplog.text
        assert openldap_group_dictionary == expected_openldap_group_dictionary
        assert ad_group_dictionary == expected_ad_group_dictionary

    def test_add_missing_openldap_groups(self) -> None:
        openldap_group_dictionary = {}
        ad_group_dictionary = {"group_1": {"id": 1}}
        AdLdapGroupSync._add_missing_openldap_groups(
            self.mocked_obj,
            openldap_group_dictionary,
            ad_group_dictionary,
        )
        assert self.mocked_obj._new_ldap_group.called

    def test_flatten_nested_group_case_1(self) -> None:
        # Object is a user
        self.mocked_obj._check_ad_object_type = MagicMock(return_value=True)
        called_groups = []
        group_members = ["some_user"]
        returned_value = AdLdapGroupSync._flatten_nested_group(
            self.mocked_obj,
            called_groups,
            group_members,
        )
        expected_value = {"some_user"}
        assert returned_value == expected_value

    """
    def side_effect_flatten_nested_group_case_2(self, ad_object, object_type) -> None:
        if ad_object == "best-group" and object_type == "group":
            return True
        if ad_object != "best-group" and object_type == "user":
            return True

    def test_flatten_nested_group_case_2(self) -> None:
        # Object is a nested group
        self.mocked_obj._check_ad_object_type = MagicMock(
            side_effect=self.side_effect_flatten_nested_group_case_2
        )
        mocked_search_result = [{"attributes": {"member": "test_user"}}]
        self.mocked_obj._group_search = MagicMock(return_value=mocked_search_result)
        called_groups = []
        group_members = [
            "CN=best-group,OU=Groups",
            "CN=John Doe,OU=Users",
            "CN=Jane Doe,OU=Users",
        ]
        returned_value = AdLdapGroupSync._flatten_nested_group(
            self.mocked_obj,
            called_groups,
            group_members,
        )
        expected_value = {"CN=Jane Doe,OU=Users", "CN=John Doe,OU=Users", "test_user"}
        assert returned_value == expected_value

    """

    def test_flatten_nested_group_case_3(self, caplog) -> None:
        # Object is neither a user or a group
        self.mocked_obj._check_ad_object_type = MagicMock(return_value=False)
        called_groups = []
        group_members = ["some_user"]
        with caplog.at_level(logging.WARNING):
            returned_value = AdLdapGroupSync._flatten_nested_group(
                self.mocked_obj,
                called_groups,
                group_members,
            )
        assert returned_value == set()
        assert "We found an object" in caplog.text

    def test_check_ad_object_type_case_1(self) -> None:
        # Not in cache
        # "user" != "group", return False
        self.mocked_obj.object_lookup_cache = {}
        expected_value = False
        self.ldap_connections["ad"].response = [
            {"attributes": {"objectClass": ["group"]}}
        ]
        ad_object = "CN=Some User,OU=Users,OU=Company,DC=Example,DC=com"
        returned_value = AdLdapGroupSync._check_ad_object_type(
            self.mocked_obj,
            ad_object,
            "user",
        )
        assert returned_value == expected_value

    def test_check_ad_object_type_case_2(self) -> None:
        # Already in cache
        # "user" == "user", return True
        ad_object = "CN=Some User,OU=Users,OU=Company,DC=Example,DC=com"
        self.mocked_obj.object_lookup_cache = {
            f"(distinguishedName={ad_object})": ["user"]
        }
        expected_value = True
        returned_value = AdLdapGroupSync._check_ad_object_type(
            self.mocked_obj,
            ad_object,
            "user",
        )
        assert returned_value == expected_value
