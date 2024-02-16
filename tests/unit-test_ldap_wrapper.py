# type: ignore
import pytest
import os
import yaml
import logging
from unittest.mock import MagicMock
from src.utils.ldap_wrapper import LdapInterface, LdapWrapper, NoOp
from ldap3 import Connection

"""
Currently all tests are just stubs !!!!!
"""

CONFIG_FILE = "tests/data/test_config.yaml"
EXCEPTIONS_FILE = "tests/data/test_exceptions.yaml"
COUNTRY_CONTROL_FILE = "tests/data/test_country_control.yaml"


class TestLdapInterface:
    @classmethod
    def setup_class(self):
        self.args = MagicMock()
        self.basic_config = {}
        self.config = yaml.safe_load(open(CONFIG_FILE, "r"))
        self.exceptions = yaml.safe_load(open(EXCEPTIONS_FILE, "r"))
        self.country_control = yaml.safe_load(open(COUNTRY_CONTROL_FILE, "r"))
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

    @staticmethod
    def remove_file(path):
        try:
            os.remove(path)
        except OSError:
            pass

    def test_init(self) -> None:
        mocked_obj = MagicMock()
        LdapInterface.__init__(mocked_obj, Connection, self.basic_config)
        assert (
            mocked_obj.manifest_path
            == self.basic_config["config"]["settings"]["manifest_path"]
        )
        assert mocked_obj.ldap_connection == Connection

    def test_unbind(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.unbind(mocked_obj)

    def test_add(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.add(mocked_obj, "some_dn")

    def test_delete(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.delete(mocked_obj, "some_dn")

    def test_modify(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.modify(mocked_obj, "some_dn", {"changes": "bla"})

    def test_modify_dn(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.modify_dn(mocked_obj, "some_dn", "relative dn")

    def test_search(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.search(mocked_obj, "search base", "search filter")

    def test_compare(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.compare(mocked_obj, "some dn", "some attribute", "a value")

    def test_abandon(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.abandon(mocked_obj, "message ID")

    def test_extended(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            LdapInterface.extended(mocked_obj, "request name")

    def test_write_manifest_good(self) -> None:
        mocked_obj = MagicMock()
        mocked_obj.manifest_path = "unit_test_manifest.log"
        LdapInterface.write_manifest(mocked_obj, "log data")
        # XXX test what is in the file
        self.remove_file("unit_test_manifest.log")

    def test_write_manifest_bad(self, caplog) -> None:
        mocked_obj = MagicMock()
        mocked_obj.manifest_path = "/can/not/write/here/unit_test_manifest.log"
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                LdapInterface.write_manifest(mocked_obj, "log data")
        # assert "unit_test_manifest.log" in caplog.text


class TestNoOp:
    def test_add(self) -> None:
        mocked_obj = MagicMock()
        NoOp.add(mocked_obj, "some_dn")

    def test_search(self) -> None:
        mocked_obj = MagicMock()
        mocked_obj.ldap_connection = MagicMock()
        mocked_obj.ldap_connection.search = MagicMock()
        NoOp.search(mocked_obj, "search base", "search filter")
        mocked_obj.ldap_connection.search.assert_called_with(
            search_base="search base",
            search_filter="search filter",
            search_scope="SUBTREE",
            dereference_aliases="ALWAYS",
            attributes=None,
            size_limit=0,
            time_limit=0,
            types_only=False,
            get_operational_attributes=False,
            controls=None,
            paged_size=None,
            paged_criticality=False,
            paged_cookie=None,
        )

    def test_modify(self) -> None:
        mocked_obj = MagicMock()
        NoOp.modify(mocked_obj, "some_dn", {"changes": "bla"})
        assert mocked_obj._result == {
            "result": 0,
            "description": "success",
            "dn": "",
            "message": "",
            "referrals": None,
            "type": "modifyResponse",
        }
        assert mocked_obj._response is None

    def test_delete(self) -> None:
        mocked_obj = MagicMock()
        with pytest.raises(NotImplementedError):
            NoOp.delete(mocked_obj, "some_dn")

    def test_response(self) -> None:
        mocked_obj = MagicMock()
        NoOp.response.fget(mocked_obj)

    def test_result(self) -> None:
        mocked_obj = MagicMock()
        NoOp.result.fget(mocked_obj)


class TestLdapWrapper:
    def test_add(self) -> None:
        mocked_obj = MagicMock()
        LdapWrapper.add(mocked_obj, "some_dn")

    def test_modify(self) -> None:
        mocked_obj = MagicMock()
        LdapWrapper.modify(mocked_obj, "some_dn", {"changes": "bla"})

    def test_search(self) -> None:
        mocked_obj = MagicMock()
        mocked_obj.ldap_connection = MagicMock()
        mocked_obj.ldap_connection.search = MagicMock()
        LdapWrapper.search(mocked_obj, "search base", "search filter")
        mocked_obj.ldap_connection.search.assert_called_with(
            search_base="search base",
            search_filter="search filter",
            search_scope="SUBTREE",
            dereference_aliases="ALWAYS",
            attributes=None,
            size_limit=0,
            time_limit=0,
            types_only=False,
            get_operational_attributes=False,
            controls=None,
            paged_size=None,
            paged_criticality=False,
            paged_cookie=None,
        )

    def test_unbind(self) -> None:
        mocked_obj = MagicMock()
        LdapWrapper.unbind(mocked_obj)
