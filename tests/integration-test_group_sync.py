# type: ignore
import copy
import logging
import pytest
from unittest.mock import MagicMock
from src.runners.group_sync import AdLdapGroupSync
from src.utils.basic_config import BasicConfig
from src.utils.manage_argument_parser import ManageParser
from src.utils.ldap_connections import LdapConnections
from unittest.mock import patch
from ldap3 import MODIFY_DELETE, MODIFY_ADD
from loguru import logger
from _pytest.logging import caplog as _caplog  # noqa


@pytest.fixture
def caplog(_caplog):  # noqa
    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message} {extra}")
    yield _caplog
    logger.remove(handler_id)


class TestIntegration:
    """
    !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!
              DO NOT RUN IN UNIVERSAL OVERRIDE WITHOUT THE PATCH
    !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!

    Patch '_build_sync_group_list' to return only the test groups when working
    with universal override.

    Else universal override will apply changes to groups we may not want to
    change at present as we are working against the production servers.
    """

    @classmethod
    def setup_class(self):
        self.mocked_obj = MagicMock()
        with patch(
            "sys.argv",
            ". group_sync --conf config/config.yaml --console error --environment prod".split(),  # noqa ignore long line
        ):
            self.args = ManageParser().parse_cli_args()
            self.basic_config = BasicConfig(self.args).create_basic_config()
        self.test_group = "ad-ldap-sync-test"
        self.openldap_group_base_string = (
            f"{self.basic_config['config']['openldap']['schema']['groups']},"
            f"{self.basic_config['config']['openldap']['schema']['base']}"
        )
        self.openldap_group_dn = (
            f"cn={self.test_group},{self.openldap_group_base_string}"
        )
        self.openldap_group_object_name = self.basic_config["config"]["openldap"][
            "schema"
        ]["objects"]["group"]["members"]
        self.expected_user_list = sorted(
            [
                "user_1",
                "user_2",
                "user_3",
                "user_4",
                "user_5",
                "user_6",
                "user_7",
                "user_8",
            ]
        )

    def setup_method(self):
        """Ensure the OpenLDAP group {test_group} is completely empty
        before each test.
        """
        user_list = []
        self.mocked_obj.basic_config = self.basic_config
        self.ldap_connections = LdapConnections().setup_ldap_connections(
            self.basic_config
        )
        self.openldap_connection = self.ldap_connections["openldap"]
        self.config = self.basic_config["config"]
        self.openldap_group_filter_string = f"(objectclass={self.config['openldap']['schema']['objects']['group']['obj_class']})"  # noqa ignore long line
        openldap_group_search_result = AdLdapGroupSync._group_search(
            self.mocked_obj,
            self.openldap_connection,
            self.openldap_group_base_string,
            self.openldap_group_filter_string,
        )
        for group in openldap_group_search_result:
            if group["attributes"]["cn"] == [self.test_group]:
                if group["attributes"].get("memberUid"):
                    user_list = group["attributes"]["memberUid"]
        group_modification = {
            self.openldap_group_object_name: [(MODIFY_DELETE, user_list)]
        }
        self.openldap_connection.modify(self.openldap_group_dn, group_modification)
        self.basic_config["args"].universal_override = False
        self.basic_config["config"]["settings"]["small_group_blind_update"] = 1

    def teardown_method(self):
        """Ensure the OpenLDAP connection is closed after each test."""
        self.openldap_connection.unbind()

    def _get_current_state(self):
        """Get a fresh state of the OpenLDAP directory."""
        openldap_group_search_result = AdLdapGroupSync._group_search(
            self.mocked_obj,
            self.openldap_connection,
            self.openldap_group_base_string,
            self.openldap_group_filter_string,
        )
        for group in openldap_group_search_result:
            if group["attributes"]["cn"] == [self.test_group]:
                if group["attributes"].get("memberUid"):
                    return group["attributes"]["memberUid"]
                else:
                    return []

    def test_case_1(self, caplog) -> None:
        """Confirm user addition works without triggering addition threshold.

        Also confirm country control list works.
        """
        user_list = [
            "user_1",
            "user_2",
            "user_3",
            "user_4",
            "user_5",
            "user_6",
            "user_8",
        ]
        group_modification = {
            self.openldap_group_object_name: [(MODIFY_ADD, user_list)]
        }
        self.openldap_connection.modify(self.openldap_group_dn, group_modification)
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.INFO):
                AdLdapGroupSync(self.basic_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        user_list.append("user_7")
        assert " MODIFY_ADD: ['user_7']" in caplog.text
        assert returned_user_list == user_list
        assert "robertl" not in returned_user_list

    def test_case_2(self, caplog) -> None:
        """Confirm triggering user addition threshold warns when no override set."""
        local_config = copy.deepcopy(self.basic_config)
        local_config["config"]["settings"]["total_change_threshold"] = 1
        local_config["config"]["settings"]["deletions_change_threshold"] = 1
        local_config["config"]["settings"]["additions_change_threshold"] = 1
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.INFO):
                AdLdapGroupSync(local_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert returned_user_list == []
        assert "Breaches thresholds but override mode not set." in caplog.text

    def test_case_3(self, caplog) -> None:
        """Confirm triggering user addition threshold works with universal override."""
        self.basic_config["args"].universal_override = True
        local_config = copy.deepcopy(self.basic_config)
        local_config["config"]["settings"]["total_change_threshold"] = 1
        local_config["config"]["settings"]["deletions_change_threshold"] = 1
        local_config["config"]["settings"]["additions_change_threshold"] = 1
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.INFO):
                AdLdapGroupSync(local_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert sorted(returned_user_list) == self.expected_user_list
        assert "Will MODIFY_ADD" in caplog.text
        assert "Running in override." in caplog.text

    def test_case_4(self, caplog) -> None:
        """Confirm triggering user addition threshold works with group override."""
        self.basic_config["args"].group_override = ["ad-ldap-sync-test"]
        local_config = copy.deepcopy(self.basic_config)
        local_config["config"]["settings"]["total_change_threshold"] = 1
        local_config["config"]["settings"]["deletions_change_threshold"] = 1
        local_config["config"]["settings"]["additions_change_threshold"] = 1
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.INFO):
                AdLdapGroupSync(local_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert sorted(returned_user_list) == self.expected_user_list
        assert "Will MODIFY_ADD" in caplog.text
        assert "Running in override." in caplog.text

    def test_case_5(self, caplog) -> None:
        """Confirm user deletion works without triggering deletion threshold."""
        local_config = copy.deepcopy(self.basic_config)
        local_config["config"]["settings"]["total_change_threshold"] = 100000
        local_config["config"]["settings"]["deletions_change_threshold"] = 100000
        local_config["config"]["settings"]["additions_change_threshold"] = 100000
        user_list = [
            "user_1",
            "user_2",
            "user_3",
            "user_4",
            "user_5",
            "user_6",
            "user_a",
        ]
        group_modification = {
            self.openldap_group_object_name: [(MODIFY_ADD, user_list)]
        }
        self.openldap_connection.modify(self.openldap_group_dn, group_modification)
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.INFO):
                AdLdapGroupSync(local_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert sorted(returned_user_list) == self.expected_user_list
        assert "Will MODIFY_DELETE" in caplog.text

    def test_case_6(self, caplog) -> None:
        """Confirm triggering user deletion threshold works with universal override."""
        self.basic_config["args"].universal_override = True
        local_config = copy.deepcopy(self.basic_config)
        local_config["config"]["settings"]["total_change_threshold"] = 1
        local_config["config"]["settings"]["deletions_change_threshold"] = 1
        local_config["config"]["settings"]["additions_change_threshold"] = 1
        user_list = [
            "user_1",
            "user_2",
            "user_3",
            "user_4",
            "user_5",
            "user_6",
            "user_a",
            "user_b",
            "user_c",
            "user_d",
            "user_e",
            "user_f",
            "user_g",
            "user_h",
            "user_i",
            "user_j",
            "user_k",
            "user_l",
            "user_m",
            "user_n",
            "user_o",
        ]
        group_modification = {
            self.openldap_group_object_name: [(MODIFY_ADD, user_list)]
        }
        self.openldap_connection.modify(self.openldap_group_dn, group_modification)
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.INFO):
                AdLdapGroupSync(local_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert sorted(returned_user_list) == self.expected_user_list
        assert "Will MODIFY_DELETE" in caplog.text
        assert "Running in override." in caplog.text

    def test_case_7(self) -> None:
        """Confirm exception list works."""
        self.basic_config["args"].universal_override = True
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            AdLdapGroupSync(self.basic_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert "user_8" in returned_user_list

    def test_case_8(self, caplog) -> None:
        """Confirm that no override is required for small groups."""
        self.basic_config["config"]["settings"]["small_group_blind_update"] = 20
        with patch(
            "src.runners.group_sync.AdLdapGroupSync._build_sync_group_list",
            return_value=["ad-ldap-sync-test"],
        ):
            with caplog.at_level(logging.DEBUG):
                AdLdapGroupSync(self.basic_config, self.ldap_connections)
        returned_user_list = self._get_current_state()
        assert sorted(returned_user_list) == self.expected_user_list
        assert "Will MODIFY_ADD" in caplog.text
        assert "Group is below small_group_blind_update threshold of 20" in caplog.text


# TODO
# Need to check if log file are written
