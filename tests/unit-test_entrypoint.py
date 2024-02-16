# type: ignore
from src.entrypoint import entrypoint
from unittest.mock import MagicMock, patch


class TestEntrypoint:
    @classmethod
    def setup_class(self):
        self.args = MagicMock()

    def setup_method(self):
        self.args.console_log_level = "INFO"
        self.args.op_type = "unit-test-entrypoint"
        self.args.environment = "noop"

    """
    @patch("src.entrypoint.AdLdapUserSync", return_value=MagicMock())
    @patch(
        "src.entrypoint.LdapConnections.setup_ldap_connections",
        return_value=MagicMock(),
    )
    @patch("src.entrypoint.ManageParser.parse_cli_args", return_value=MagicMock())
    def test_entrypoint_user_sync(self, mock_args, mock_ldap, mock_sync) -> None:
        self.args.op_type = "user_sync"
        basic_config_user_sync = {"args": self.args}
        with patch(
            "src.entrypoint.BasicConfig.create_basic_config",
            return_value=basic_config_user_sync,
        ):
            entrypoint()

    @patch("src.entrypoint.AdLdapGroupSync", return_value=MagicMock())
    @patch(
        "src.entrypoint.LdapConnections.setup_ldap_connections",
        return_value=MagicMock(),
    )
    @patch("src.entrypoint.ManageParser.parse_cli_args", return_value=MagicMock())
    def test_entrypoint_group_sync(self, mock_args, mock_ldap, mock_sync) -> None:
        self.args.op_type = "group_sync"
        basic_config_group_sync = {"args": self.args}
        with patch(
            "src.entrypoint.BasicConfig.create_basic_config",
            return_value=basic_config_group_sync,
        ):
            entrypoint()
    """
