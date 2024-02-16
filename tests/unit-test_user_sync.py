# type: ignore
import logging
import os
import yaml
import re
import pytest
import string
import operator
import copy
from loguru import logger
from src.runners.user_sync import AdLdapUserSync
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


class TestUserSync:
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
        self.args.op_type = "unit-test-user-sync"
        self.args.environment = "noop"
        self.basic_config = {
            "config": self.config,
            "exceptions": self.exceptions,
            "country_control": self.country_control,
            "args": self.args,
        }
        self.mocked_obj.basic_config = self.basic_config

    def test_get_user_attributes(self) -> None:
        expected_value = {
            "ad": [
                "c",
                "cn",
                "displayName",
                "gecos",
                "gidNumber",
                "givenName",
                "loginShell",
                "mail",
                "sAMAccountName",
                "sn",
                "uid",
                "uidNumber",
                "unixHomeDirectory",
                "userAccountControl",
            ],
            "openldap": [
                "cn",
                "displayName",
                "gecos",
                "gidNumber",
                "givenName",
                "homeDirectory",
                "loginShell",
                "mail",
                "objectClass",
                "sambaAcctFlags",
                "sambaSid",
                "sn",
                "sshPublicKey",
                "uid",
                "uidNumber",
            ],
        }
        returned_value = AdLdapUserSync._get_user_attributes(self.mocked_obj)
        assert returned_value == expected_value
        # As there is currently a delete on a copied dict,
        # ensure we don't impact the original dict.
        assert len(self.mocked_obj.ldap_connections) == 2

    def test_convert_lists_to_strings_case_1(self) -> None:
        # Test converting an empty list to an empty string.
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": ["johnd@example.com"],
                    "unixHomeDirectory": [],
                    "userAccountControl": 512,
                }
            }
        }
        expected_all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": "johnd@example.com",
                    "unixHomeDirectory": "",
                    "userAccountControl": 512,
                }
            }
        }
        AdLdapUserSync._convert_lists_to_strings(self.mocked_obj)
        assert expected_all_users == self.mocked_obj.all_users

    def test_convert_lists_to_strings_case_2(self) -> None:
        # Test converting a list with a single string entry to a string.
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": ["johnd@example.com"],
                    "unixHomeDirectory": ["/home/johnd"],
                    "userAccountControl": 512,
                }
            }
        }
        expected_all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": "johnd@example.com",
                    "unixHomeDirectory": "/home/johnd",
                    "userAccountControl": 512,
                }
            }
        }
        AdLdapUserSync._convert_lists_to_strings(self.mocked_obj)
        assert expected_all_users == self.mocked_obj.all_users

    def test_convert_lists_to_strings_case_3(self) -> None:
        # Test converting a list with a single byte object entry to a string.
        # This is for the SSH keys that OpenLDAP stores in byte strings.
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": ["johnd@example.com"],
                    "unixHomeDirectory": [b"/home/johnd"],
                    "userAccountControl": 512,
                }
            }
        }
        expected_all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": "johnd@example.com",
                    "unixHomeDirectory": "/home/johnd",
                    "userAccountControl": 512,
                }
            }
        }
        AdLdapUserSync._convert_lists_to_strings(self.mocked_obj)
        assert expected_all_users == self.mocked_obj.all_users

    def test_convert_lists_to_strings_case_4(self, caplog) -> None:
        # Test that we exit if there is more than one entry in the array.
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": ["johnd@example.com"],
                    "unixHomeDirectory": [b"/home/johnd", "some_entry"],
                    "userAccountControl": 512,
                }
            }
        }
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                AdLdapUserSync._convert_lists_to_strings(self.mocked_obj)
        assert "Found array with more than one entry" in caplog.text

    def test_get_all_users(self) -> None:
        self.mocked_obj.all_users = {}
        self.mocked_obj.ldap_connections["ad"].response = [
            {
                "dn": "CN=John Doe,OU=Users,OU=Company,DC=example,DC=com",
                "attributes": {
                    "cn": "John Doe",
                    "sn": "John",
                    "c": "GB",
                    "givenName": "Doe",
                    "displayName": "John Doe",
                    "userAccountControl": 512,
                    "sAMAccountName": "johnd",
                    "mail": "johnd@example.com",
                    "gecos": [],
                    "gidNumber": [],
                    "loginShell": [],
                    "uid": [],
                    "uidNumber": [],
                    "unixHomeDirectory": [],
                },
            },
        ]
        expected_all_users = {
            "johnd": {
                "ad": {
                    "c": "GB",
                    "changes": {},
                    "cn": "John Doe",
                    "displayName": "John Doe",
                    "dn": "CN=John Doe,OU=Users,OU=Company,DC=example,DC=com",
                    "gecos": [],
                    "gidNumber": [],
                    "givenName": "Doe",
                    "loginShell": [],
                    "mail": "johnd@example.com",
                    "sAMAccountName": "johnd",
                    "sn": "John",
                    "uid": [],
                    "uidNumber": [],
                    "unixHomeDirectory": [],
                    "userAccountControl": 512,
                },
            }
        }
        AdLdapUserSync._get_all_users(self.mocked_obj)
        assert expected_all_users == self.mocked_obj.all_users

    def test_attr_ascii_compare_openldap(self) -> None:
        all_users = yaml.safe_load(open("tests/data/all_test_users.yaml", "r"))
        self.mocked_obj.all_users = all_users
        all_users_with_changes = yaml.safe_load(
            open("tests/data/all_test_users_with_changes.yaml", "r")
        )
        synced_attrs = {"givenName": "givenName", "gecos": "gecos"}
        for attr in synced_attrs:
            returned_value = AdLdapUserSync._attr_ascii_compare(
                self.mocked_obj, "bos", "ad", attr, "openldap", synced_attrs
            )
            assert (
                all_users_with_changes["bos"]["openldap"]["changes"][attr]
                == returned_value
            )

    def test_attr_ascii_compare_ad(self) -> None:
        all_users = yaml.safe_load(open("tests/data/all_test_users.yaml", "r"))
        self.mocked_obj.all_users = all_users
        all_users_with_changes = yaml.safe_load(
            open("tests/data/all_test_users_with_changes.yaml", "r")
        )
        synced_attrs = {"displayName": "gecos"}
        for attr in synced_attrs:
            returned_value = AdLdapUserSync._attr_ascii_compare(
                self.mocked_obj, "bos", "ad", attr, "ad", synced_attrs
            )
            assert (
                all_users_with_changes["bos"]["ad"]["changes"]["gecos"]
                == returned_value
            )

    def test_attr_ascii_compare_none(self) -> None:
        all_users = {
            "johnd": {
                "ad": {
                    "uid": "",
                    "uidNumber": "abc_string",
                    "unixHomeDirectory": [],
                    "userAccountControl": 512,
                },
                "openldap": {
                    "uidNumber": "abc_string",
                },
            }
        }
        self.mocked_obj.all_users = all_users
        synced_attrs = {"uid": "uid", "uidNumber": "uidNumber"}
        for server_type in ["ad", "openldap"]:
            for attr in synced_attrs:
                returned_value = AdLdapUserSync._attr_ascii_compare(
                    self.mocked_obj, "johnd", "ad", attr, server_type, synced_attrs
                )
                assert returned_value is None

    def test_build_attr_changes(self) -> None:
        # XXX This unit test should be better.
        # We really need to read in tests/data/all_test_users_with_changes.yaml
        # and compare.
        all_users = yaml.safe_load(open("tests/data/all_test_users.yaml", "r"))
        self.mocked_obj.all_users = all_users
        self.mocked_obj._attr_ascii_compare = MagicMock()
        AdLdapUserSync._build_attr_changes(
            self.mocked_obj, "ad", "ad", "local_copy_attrs"
        )
        AdLdapUserSync._build_attr_changes(
            self.mocked_obj, "ad", "openldap", "remote_synced_attrs"
        )
        AdLdapUserSync._build_attr_changes(
            self.mocked_obj, "openldap", "openldap", "local_copy_attrs"
        )
        AdLdapUserSync._build_attr_changes(
            self.mocked_obj, "openldap", "ad", "remote_synced_attrs"
        )
        self.mocked_obj._attr_ascii_compare.assert_called_with(
            "janed",
            "openldap",
            "uid",
            "ad",
            {
                "sambaAcctFlags": "c",
                "uidNumber": "uidNumber",
                "gidNumber": "gidNumber",
                "loginShell": "loginShell",
                "homeDirectory": "unixHomeDirectory",
                "uid": "uid",
            },
        )

    def test_get_next_sambasid(self, caplog) -> None:
        # Make sure not to return 1642, the gap.
        test_data = [
            {
                "attributes": {"sambaSID": "badtext"},
            },
            {
                "attributes": {
                    "sambaSID": "S-1-2-34-5678901234-5678918346-164430003-1857"
                },
            },
            {
                "attributes": {
                    "sambaSID": "S-1-2-34-5678901234-5678918346-164430003-1857"
                },
            },
        ]
        self.mocked_obj.ldap_connections["openldap"].response = test_data
        with caplog.at_level(logging.WARNING):
            returned_value = AdLdapUserSync._get_next_sambasid(self.mocked_obj)
        assert returned_value == "S-1-2-34-5678901234-5678918346-164430003-1857"
        assert "badtext" in caplog.text

    def test_set_random_ldap_password_both_passwords(self) -> None:
        self.mocked_obj._generate_password = MagicMock(return_value="some_password")
        self.mocked_obj.all_users = {"johnd": {"openldap": {"changes": {}}}}
        returned_value = AdLdapUserSync._set_random_ldap_password(
            self.mocked_obj,
            "openldap",
            "johnd",
            ["sambaNTPassword", "userPassword"],
        )
        assert returned_value == "some_password"
        assert (
            self.mocked_obj.all_users["johnd"]["openldap"]["changes"]["userPassword"][
                :10
            ]
            == b"{CRYPT}$6$"
        )
        # Not sure how to test that the above have a salt.
        # Might need to look for data after the password type and the actual password.
        assert (
            "sambaNTPassword"
            in self.mocked_obj.all_users["johnd"]["openldap"]["changes"].keys()
        )
        # There is no salt on the AD password :( :( :(
        assert (
            self.mocked_obj.all_users["johnd"]["openldap"]["changes"]["sambaNTPassword"]
            == "DA1A13528CBAC31610F3CAC50F1694B1"
        )

    def test_set_random_ldap_password_only_sambaNTPassword(self) -> None:
        self.mocked_obj._generate_password = MagicMock(return_value="some_password")
        self.mocked_obj.all_users = {"johnd": {"openldap": {"changes": {}}}}
        returned_value = AdLdapUserSync._set_random_ldap_password(
            self.mocked_obj,
            "openldap",
            "johnd",
            ["sambaNTPassword"],
        )
        assert returned_value == "some_password"
        assert (
            "userPassword"
            not in self.mocked_obj.all_users["johnd"]["openldap"]["changes"].keys()
        )
        assert (
            "sambaNTPassword"
            in self.mocked_obj.all_users["johnd"]["openldap"]["changes"].keys()
        )
        assert (
            self.mocked_obj.all_users["johnd"]["openldap"]["changes"]["sambaNTPassword"]
            == "DA1A13528CBAC31610F3CAC50F1694B1"
        )

    def test_set_random_ldap_password_only_userPassword(self) -> None:
        self.mocked_obj._generate_password = MagicMock(return_value="some_password")
        self.mocked_obj.all_users = {"johnd": {"openldap": {"changes": {}}}}
        returned_value = AdLdapUserSync._set_random_ldap_password(
            self.mocked_obj,
            "openldap",
            "johnd",
            ["userPassword"],
        )
        assert returned_value == "some_password"
        assert (
            self.mocked_obj.all_users["johnd"]["openldap"]["changes"]["userPassword"][
                :10
            ]
            == b"{CRYPT}$6$"
        )
        assert (
            "sambaNTPassword"
            not in self.mocked_obj.all_users["johnd"]["openldap"]["changes"].keys()
        )

    def test_generate_password_good(self) -> None:
        # This might take a couple of seconds, but provides some confidence
        # We really need statistical modeling. Unfortunately the options available
        # seems problematic in the Alpine container.
        returned_values = []
        for i in range(10000):
            returned_values.append(AdLdapUserSync._generate_password(self.mocked_obj))
        specials = self.basic_config["config"]["settings"][
            "special_password_characters"
        ]
        escaped_specials = f"[{re.escape(specials)}]"
        for value in returned_values:
            assert re.search("[A-Z]", value)
            assert re.search("[a-z]", value)
            assert re.search("[0-9]", value)
            assert re.search(escaped_specials, value)
        assert len(set(returned_values)) == len(returned_values)

    def test_generate_password_fail(self, caplog) -> None:
        self.mocked_obj.basic_config["config"]["settings"]["banned_password_chars"] = (
            string.ascii_letters + string.digits
        )
        with caplog.at_level(logging.ERROR):
            with pytest.raises(SystemExit):
                AdLdapUserSync._generate_password(self.mocked_obj)
        assert "Unable" in caplog.text

    def test_update_ldap_account_good(self, caplog) -> None:
        self.mocked_obj.ldap_connections["openldap"].result = {"result": 0}
        self.mocked_obj.all_users = {
            "johnd": {
                "openldap": {
                    "changes": {"gecos": "test", "displayName": "bob"},
                    "dn": "some DN",
                }
            }
        }
        expected_all_users = {
            "johnd": {
                "openldap": {
                    "changes": {
                        "displayName": [("MODIFY_REPLACE", ["bob"])],
                        "gecos": [("MODIFY_REPLACE", ["test"])],
                    },
                    "dn": "some DN",
                }
            }
        }
        with caplog.at_level(logging.INFO):
            AdLdapUserSync._update_ldap_account(self.mocked_obj, "johnd")
        assert self.mocked_obj.all_users == expected_all_users
        assert "johnd" in caplog.text
        assert "openldap" in caplog.text
        assert "gecos" in caplog.text

    def test_update_ldap_account_fail(self, caplog) -> None:
        self.mocked_obj.run_status = True
        self.mocked_obj.ldap_connections["openldap"].result = {
            "result": 1,
            "description": "All bad",
        }
        self.mocked_obj.all_users = {
            "johnd": {
                "openldap": {
                    "changes": {"gecos": "test", "displayName": "bob"},
                    "dn": "some DN",
                }
            }
        }
        with caplog.at_level(logging.ERROR):
            AdLdapUserSync._update_ldap_account(self.mocked_obj, "johnd")
        assert "johnd" in caplog.text
        assert "All bad" in caplog.text
        assert self.mocked_obj.run_status is False

    def set_test_password(self, user, password, mocked_obj) -> str:
        mocked_obj.all_users[user]["openldap"]["changes"]["userPassword"] = password
        mocked_obj.all_users[user]["openldap"]["changes"]["sambaNTPassword"] = password

    def test_new_ldap_account_good(self, caplog) -> None:
        self.mocked_obj._get_next_sambasid = MagicMock(return_value="S-123")
        self.mocked_obj._get_next_ldap_uid_number = MagicMock(return_value="456")
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "dn": "some DN",
                },
                "openldap": {"changes": {}},
            }
        }
        self.mocked_obj.ldap_connections["openldap"].result = {"result": 0}
        original_mask = copy.deepcopy(
            self.basic_config["config"]["openldap"]["schema"]["new_user"]["mask"]
        )
        expected_all_users = {
            "johnd": {
                "ad": {
                    "dn": "some DN",
                },
                "openldap": {
                    "changes": {
                        "sambaNTPassword": "ffs",
                        "userPassword": "ffs",
                    },
                    "cn": "johnd",
                    "displayName": "NEW USER",
                    "dn": "uid=johnd,ou=People,dc=example,dc=com",
                    "gecos": "NEW USER",
                    "gidNumber": 501,
                    "givenName": "NEW",
                    "homeDirectory": "/home/johnd",
                    "loginShell": "/bin/bash",
                    "mail": "newuser@example.com",
                    "sambaAcctFlags": "[U          ]",
                    "sambaSID": "S-123",
                    "sn": "USER",
                    "uid": "johnd",
                    "uidNumber": "456",
                },
            }
        }
        with caplog.at_level(logging.INFO):
            with patch("utils.utilities.get_next_gid_uid_number", return_value="456"):
                AdLdapUserSync._new_ldap_account(
                    self.mocked_obj,
                    "openldap",
                    "johnd",
                )
        self.mocked_obj._set_random_ldap_password = MagicMock(
            return_value="ffs",
            side_effect=self.set_test_password("johnd", "ffs", self.mocked_obj),
        )
        # XXX I don't understand why the above mock has to be defined after the method?
        #     It is executing on definition instead of on call.
        assert "johnd" in caplog.text
        assert self.mocked_obj.ldap_connections["openldap"].add.called
        assert self.mocked_obj.all_users == expected_all_users
        assert (
            original_mask
            == self.basic_config["config"]["openldap"]["schema"]["new_user"]["mask"]
        )

    def test_new_ldap_account_fail(self, caplog) -> None:
        self.mocked_obj.ldap_connections["openldap"].result = {"result": 1}
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "dn": "some DN",
                }
            }
        }
        with caplog.at_level(logging.ERROR):
            with patch("utils.utilities.get_next_gid_uid_number", return_value=1):
                AdLdapUserSync._new_ldap_account(
                    self.mocked_obj,
                    "openldap",
                    "johnd",
                )
        assert "johnd" in caplog.text
        assert "1" in caplog.text
        assert self.mocked_obj.ldap_connections["openldap"].add.called
        assert self.mocked_obj.run_status is False

    def test_check_change_disable(self, caplog) -> None:
        self.mocked_obj._set_random_ldap_password = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {},
                "openldap": {
                    "changes": {},
                    "loginShell": "/bin/bash",
                    "sambaAcctFlags": "[U          ]",
                    "sshPublicKey": '[b"ecdsa-sha256 KEY"]',
                },
            }
        }
        expected_all_users = {
            "johnd": {
                "ad": {},
                "openldap": {
                    "changes": {
                        "loginShell": "/sbin/nologin",
                        "sambaAcctFlags": "[DU         ]",
                        "sshPublicKey": "non valid public ssh key",
                    },
                    "loginShell": "/bin/bash",
                    "sambaAcctFlags": "[U          ]",
                    "sshPublicKey": '[b"ecdsa-sha256 KEY"]',
                },
            }
        }
        with caplog.at_level(logging.INFO):
            AdLdapUserSync._check_change(
                self.mocked_obj, "johnd", operator.ne, "disable_user_mask"
            )
        assert expected_all_users == self.mocked_obj.all_users
        assert self.mocked_obj._set_random_ldap_password.called
        assert "johnd" in caplog.text

    def test_check_change_enable_1(self, caplog) -> None:
        # Change all normal disabled entries to enabled
        self.mocked_obj._set_random_ldap_password = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {},
                "openldap": {
                    "changes": {},
                    "loginShell": "/sbin/nologin",
                    "sambaAcctFlags": "[DU         ]",
                    "sshPublicKey": '[b"ecdsa-sha256 KEY"]',
                },
            }
        }
        expected_all_users = {
            "johnd": {
                "ad": {},
                "openldap": {
                    "changes": {
                        "loginShell": "/bin/bash",
                        "sambaAcctFlags": "[U          ]",
                    },
                    "loginShell": "/sbin/nologin",
                    "sambaAcctFlags": "[DU         ]",
                    "sshPublicKey": '[b"ecdsa-sha256 KEY"]',
                },
            }
        }
        with caplog.at_level(logging.INFO):
            AdLdapUserSync._check_change(
                self.mocked_obj, "johnd", operator.eq, "enable_user_mask"
            )
        assert expected_all_users == self.mocked_obj.all_users
        assert self.mocked_obj._set_random_ldap_password.called
        assert "johnd" in caplog.text

    def test_check_change_enable_2(self, caplog) -> None:
        # Don't change items that are not matched
        self.mocked_obj._set_random_ldap_password = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {},
                "openldap": {
                    "changes": {},
                    "loginShell": "/bin/random_shell",
                    "sambaAcctFlags": "[DU         ]",
                    "sshPublicKey": '[b"ecdsa-sha256 KEY"]',
                },
            }
        }
        expected_all_users = {
            "johnd": {
                "ad": {},
                "openldap": {
                    "changes": {
                        "sambaAcctFlags": "[U          ]",
                    },
                    "loginShell": "/bin/random_shell",
                    "sambaAcctFlags": "[DU         ]",
                    "sshPublicKey": '[b"ecdsa-sha256 KEY"]',
                },
            }
        }
        with caplog.at_level(logging.INFO):
            AdLdapUserSync._check_change(
                self.mocked_obj, "johnd", operator.eq, "enable_user_mask"
            )
        assert expected_all_users == self.mocked_obj.all_users
        assert self.mocked_obj._set_random_ldap_password.called
        assert "johnd" in caplog.text

    def test_check_user_enable_disable_1(self) -> None:
        # Check that we disable a user.
        self.mocked_obj._check_change = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {"userAccountControl": 404},
                "openldap": {"uid": "johnd", "objectClass": ["top"]},
            }
        }
        AdLdapUserSync._check_user_enable_disable(self.mocked_obj)
        self.mocked_obj._check_change.assert_called_with(
            "johnd", operator.ne, "disable_user_mask"
        )

    def test_check_user_enable_disable_2(self) -> None:
        # Check that we enable a user.
        self.mocked_obj._check_change = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {"userAccountControl": 512},
                "openldap": {"uid": "johnd", "objectClass": ["top"]},
            }
        }
        AdLdapUserSync._check_user_enable_disable(self.mocked_obj)
        self.mocked_obj._check_change.assert_called_with(
            "johnd", operator.eq, "enable_user_mask"
        )

    def test_check_user_enable_disable_3(self) -> None:
        # Create OpenLDAP account.
        self.mocked_obj._new_ldap_account = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {"userAccountControl": 512},
            }
        }
        AdLdapUserSync._check_user_enable_disable(self.mocked_obj)
        self.mocked_obj._new_ldap_account.assert_called_with("openldap", "johnd")

    def test_check_user_enable_disable_4(self, caplog) -> None:
        # Note that MS AD account is required.
        self.mocked_obj.all_users = {
            "johnd": {
                "openldap": {"uid": "johnd"},
            }
        }
        with caplog.at_level(logging.DEBUG):
            AdLdapUserSync._check_user_enable_disable(self.mocked_obj)
        assert "MS AD account missing" in caplog.text

    def test_main_called(self) -> None:
        self.mocked_obj._main = MagicMock()
        AdLdapUserSync.__init__(
            self.mocked_obj, self.basic_config, self.ldap_connections
        )
        assert self.mocked_obj._main.called

    def test_main(self) -> None:
        self.mocked_obj._update_ldap_account = MagicMock()
        self.mocked_obj.all_users = {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "mail": ["johnd@example.com"],
                    "unixHomeDirectory": [],
                    "userAccountControl": 512,
                }
            }
        }
        with patch("utils.utilities.user_exception_lookup"):
            AdLdapUserSync._main(self.mocked_obj)
        self.mocked_obj._build_attr_changes.assert_any_call(
            source_server_type="ad",
            destination_server_type="ad",
            attr_type="local_copy_attrs",
        )
        self.mocked_obj._build_attr_changes.assert_any_call(
            source_server_type="ad",
            destination_server_type="openldap",
            attr_type="remote_synced_attrs",
        )
        self.mocked_obj._build_attr_changes.assert_any_call(
            source_server_type="openldap",
            destination_server_type="openldap",
            attr_type="local_copy_attrs",
        )
        self.mocked_obj._build_attr_changes.assert_any_call(
            source_server_type="openldap",
            destination_server_type="ad",
            attr_type="remote_synced_attrs",
        )
        self.remove_file("user_sync_test_monitoring.log")
        assert self.mocked_obj._update_ldap_account.called
        # XXX Need to check that the monitoring log file was correctly written

    def test_add_class_to_ldap_account_good_case_1(self, caplog) -> None:
        # Testing for sambaSamAccount class
        self.mocked_obj._get_next_sambasid = MagicMock(return_value="some_samba_sid")
        self.mocked_obj._set_random_ldap_password = MagicMock(
            return_value="some_random_pass"
        )
        self.mocked_obj.ldap_connections["openldap"].result = {"result": 0}
        with caplog.at_level(logging.INFO):
            AdLdapUserSync._add_class_to_ldap_account(
                self.mocked_obj,
                "openldap",
                "bob",
                "sambaSamAccount",
            )
        assert "Will add 'sambaSamAccount' class for" in caplog.text
        self.mocked_obj.ldap_connections["openldap"].modify.assert_called_with(
            "uid=bob,ou=People,dc=example,dc=com",
            {
                "objectClass": [("MODIFY_ADD", ["sambaSamAccount"])],
                "sambaSid": [("MODIFY_ADD", "some_samba_sid")],
            },
        )

    def test_add_class_to_ldap_account_good_case_2(self, caplog) -> None:
        # Testing for any other class
        self.mocked_obj._get_next_sambasid = MagicMock(return_value="some_samba_sid")
        self.mocked_obj._set_random_ldap_password = MagicMock(
            return_value="some_random_pass"
        )
        self.ldap_connections["openldap"].result = {"result": 0}
        self.ldap_connections["openldap"].modify = MagicMock()
        with caplog.at_level(logging.INFO):
            AdLdapUserSync._add_class_to_ldap_account(
                self.mocked_obj,
                "openldap",
                "bob",
                "top",
            )
        assert "Will add 'top' class for" in caplog.text
        self.ldap_connections["openldap"].modify.assert_called_with(
            "uid=bob,ou=People,dc=example,dc=com",
            {"objectClass": [("MODIFY_ADD", ["top"])]},
        )

    def test_add_class_to_ldap_account_bad(self, caplog) -> None:
        self.ldap_connections["openldap"].result = {
            "result": 1,
            "description": "Bad things",
        }
        with caplog.at_level(logging.ERROR):
            AdLdapUserSync._add_class_to_ldap_account(
                self.mocked_obj,
                "openldap",
                "bob",
                "top",
            )
        assert "Bad things" in caplog.text
        assert self.mocked_obj.run_status is False
