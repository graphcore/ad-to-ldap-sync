# type: ignore
import os
import ssl
import copy
import logging
import yaml
import pytest
from unittest.mock import MagicMock, patch
from src.utils.ldap_connections import LdapConnections
from ldap3 import Server, Tls
from _pytest.logging import caplog as _caplog  # noqa
from loguru import logger

CONFIG_FILE = "tests/data/test_config.yaml"
EXCEPTIONS_FILE = "tests/data/test_exceptions.yaml"
COUNTRY_CONTROL_FILE = "tests/data/test_country_control.yaml"
BAD_CONFIG_FILE = "tests/data/test_bad_config.yaml"


@pytest.fixture
def caplog(_caplog):  # noqa
    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    handler_id = logger.add(PropagateHandler(), format="{message} {extra}")
    yield _caplog
    logger.remove(handler_id)


class TestLdapConnections:
    @classmethod
    def setup_class(self):
        self.args = MagicMock()
        self.basic_config = {}
        self.config = yaml.safe_load(open(CONFIG_FILE, "r"))
        self.exceptions = yaml.safe_load(open(EXCEPTIONS_FILE, "r"))
        self.country_control = yaml.safe_load(open(COUNTRY_CONTROL_FILE, "r"))
        self.bad_config = yaml.safe_load(open(BAD_CONFIG_FILE, "r"))
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
        self.logger = logging.getLogger()
        self.basic_config = {
            "logger": self.logger,
            "config": self.config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }

        self.tls_configuration = Tls(
            ciphers="ALL",
            validate=getattr(ssl, self.config["openldap"]["ssl"]["validate"]),
            version=getattr(ssl, self.config["openldap"]["ssl"]["version"]),
        )

        self.ldap_server = Server(
            self.config["openldap"]["server"],
            port=self.config["openldap"]["port"],
            use_ssl=self.config["openldap"]["ssl"]["enabled"],
            tls=self.tls_configuration,
            get_info=self.config["openldap"]["get_info"],
        )

    def teardown_method(self):
        self.remove_file(
            f"{self.args.op_type}_"
            f"{self.basic_config['config']['settings']['monitoring_log_file']}"
        )
        self.remove_file("user_sync_test_monitoring.log")
        self.remove_file("group_sync_test_monitoring.log")

    @staticmethod
    def remove_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def mocked_bind_to_broken_openldap(self, basic_config, server_type):
        mocked_obj = MagicMock()
        if server_type == "openldap":
            mocked_obj.result = {"result": 49}
            return mocked_obj
        else:
            mocked_obj.result = {"result": 0}
            return mocked_obj

    def mocked_bind_to_broken_ad(self, basic_config, server_type):
        mocked_obj = MagicMock()
        if server_type == "openldap":
            mocked_obj.result = {"result": 0}
            return mocked_obj
        else:
            mocked_obj.result = {"result": 49}
            return mocked_obj

    def test_setup_ldap_connections_case_1(self, caplog) -> None:
        # Bad OpenLDAP connection
        mocked_obj = MagicMock()
        mocked_obj._bind_to_ldap = self.mocked_bind_to_broken_openldap
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                LdapConnections.setup_ldap_connections(mocked_obj, self.basic_config)
        assert len(caplog.text) > 0

    def test_setup_ldap_connections_case_2(self, caplog) -> None:
        # Bad MS AD connection
        mocked_obj = MagicMock()
        mocked_obj._bind_to_ldap = self.mocked_bind_to_broken_ad
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                LdapConnections.setup_ldap_connections(mocked_obj, self.basic_config)
        assert len(caplog.text) > 0

    def test_setup_ldap_connections_case_3(self, caplog) -> None:
        # Bad OpenLDAP & MS AD connections
        mocked_obj = MagicMock()
        mocked_return = MagicMock()
        mocked_return.result = {"result": 49}
        mocked_obj._bind_to_ldap = MagicMock(return_value=mocked_return)
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                LdapConnections.setup_ldap_connections(mocked_obj, self.basic_config)
        assert len(caplog.text) > 0
        assert mocked_obj._bind_to_ldap.called

    def test_setup_ldap_connections_good(self, caplog) -> None:
        mocked_obj = MagicMock()
        mocked_return = MagicMock()
        mocked_return.result = {"result": 0}
        mocked_obj._bind_to_ldap = MagicMock(return_value=mocked_return)
        returned_data = LdapConnections.setup_ldap_connections(mocked_obj, self.args)
        assert mocked_obj._bind_to_ldap.called
        assert "ad" in returned_data
        assert "openldap" in returned_data

    def test_create_tls_object_good(self) -> None:
        tls_configuration = LdapConnections._create_tls_object(
            self.basic_config,
            "openldap",
        )
        assert tls_configuration.__dict__["validate"] == 0
        assert tls_configuration.__dict__["version"] == 5

    def test_create_tls_object_bad(self, caplog) -> None:
        mocked_write_monitoring_log = MagicMock()
        bad_basic_config = {
            "logger": self.logger,
            "config": self.bad_config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                with patch(
                    "utils.utilities.write_monitoring_log",
                ) as mocked_write_monitoring_log:
                    LdapConnections._create_tls_object(bad_basic_config, "openldap")
                    assert mocked_write_monitoring_log.called
        assert len(caplog.text) > 0
        # mocked_write_monitoring_log.assert_called_once_with(basic_config, False) # XXX
        # assert mocked_obj.run_status is False # XXX

    def test_create_ldap_server_object_good(self) -> None:
        mocked_obj = MagicMock()
        ldap_server = LdapConnections._create_ldap_server_object(
            mocked_obj,
            self.basic_config,
            self.tls_configuration,
            "openldap",
        )
        assert ldap_server.__dict__["host"] == self.config["openldap"]["server"]
        assert ldap_server.__dict__["port"] == self.config["openldap"]["port"]
        assert ldap_server.__dict__["get_info"] == self.config["openldap"]["get_info"]
        assert ldap_server.__dict__["name"] == (
            f"ldaps://{self.config['openldap']['server']}:"
            f"{str(self.config['openldap']['port'])}"
        )

    def test_create_ldap_server_object_bad(self, caplog) -> None:
        mocked_obj = MagicMock()
        local_bad_config = copy.deepcopy(self.bad_config)
        local_bad_config["openldap"]["port"] = "bad_config"
        bad_basic_config = {
            "logger": self.logger,
            "config": local_bad_config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }
        mocked_obj._write_monitoring_log = MagicMock()
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                with patch(
                    "utils.utilities.write_monitoring_log",
                ) as mocked_write_monitoring_log:
                    LdapConnections._create_ldap_server_object(
                        mocked_obj,
                        bad_basic_config,
                        self.tls_configuration,
                        "openldap",
                    )
                    assert mocked_write_monitoring_log.called
        assert len(caplog.text) > 0
        # mocked_write_monitoring_log.assert_called_once_with(basic_config, False) # XXX
        # assert mocked_obj.run_status is False # XXX

    def test_create_ldap_connection_object_good(self) -> None:
        mocked_obj = MagicMock()
        connection = LdapConnections._create_ldap_connection_object(
            mocked_obj,
            self.basic_config,
            self.ldap_server,
            "openldap",
        )
        assert connection.__dict__["user"] == self.config["openldap"]["bind_user"]
        assert connection.__dict__["password"] == self.config["openldap"]["bind_pass"]

    def test_create_ldap_connection_object_bad(self, caplog) -> None:
        mocked_obj = MagicMock()
        local_bad_config = copy.deepcopy(self.bad_config)
        local_bad_config["openldap"].pop("bind_user")
        mocked_obj._write_monitoring_log = MagicMock()
        bad_basic_config = {
            "logger": self.logger,
            "config": local_bad_config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                with patch(
                    "utils.utilities.write_monitoring_log",
                ) as mocked_write_monitoring_log:
                    LdapConnections._create_ldap_connection_object(
                        mocked_obj,
                        bad_basic_config,
                        self.ldap_server,
                        "openldap",
                    )
                    assert mocked_write_monitoring_log.called
        assert len(caplog.text) > 0
        # mocked_write_monitoring_log.assert_called_once_with(basic_config, False) # XXX

    def test_bind_to_ldap_good(self) -> None:
        mocked_obj = MagicMock()
        mocked_return = MagicMock()
        mocked_obj._create_ldap_connection_object = MagicMock(
            return_value=mocked_return
        )
        mocked_return.bind = MagicMock()
        self.args.environment = "prod"
        with patch(
            "src.utils.ldap_connections.CONNECTION_WRAPPER_REFERENCE",
            {"prod": mocked_return},
        ):
            LdapConnections._bind_to_ldap(mocked_obj, self.basic_config, "openldap")
        assert mocked_return.bind.called

    def test_bind_to_ldap_bad(self, caplog) -> None:
        mocked_obj = MagicMock()
        mocked_raise = MagicMock()
        mocked_obj._create_ldap_connection_object = MagicMock(return_value=mocked_raise)
        mocked_raise.bind = MagicMock(side_effect=Exception("exc output"))
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                with patch(
                    "utils.utilities.write_monitoring_log",
                ) as mocked_write_monitoring_log:
                    LdapConnections._bind_to_ldap(
                        mocked_obj, self.basic_config, "openldap"
                    )
                    assert mocked_write_monitoring_log.called
        assert len(caplog.text) > 0
        # mocked_write_monitoring_log.assert_called_once_with(basic_config, False) # XXX
