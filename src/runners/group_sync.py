"""This module is used to synchronize groups between MS AD to OpenLDAP."""
from ldap3 import (
    Connection,
    MODIFY_ADD,
    MODIFY_DELETE,
    MODIFY_REPLACE,
    SUBTREE,
)
import copy
import sys
import utils.utilities as Utilities
from loguru import logger
from typing import Any, Optional
from utils.manage_argument_parser import ManageArguments


class AdLdapGroupSync:
    """Groups from a specific OU’s are synchronised (created/modified) between the
    directories.

    - There are country control methods implemented for data export control.
    - All nested groups are flattened.
    - Protection is in place so that large change sets requires manual intervention.
    - Regardless of group or user synchronisation, users are checked against an
      exception lookup table.

    Parameters
    ----------
    basic_config : dict[str, Any]
        A dictionary containing all the basic configuration settings.
    ldap_connections : dict[str, Connection]
        A dictionary containing all the LDAP connections.
    """

    user_lookup_cache: dict[str, dict[str, Any]] = {}
    """The main cache for all the users."""
    run_status: bool = True
    """The overall run status of the script. Set to false anytime something goes
    wrong."""
    object_lookup_cache: dict[str, Any] = {}
    """The main cache for recursive lookup during flattening of groups."""

    def __init__(
        self, basic_config: dict[str, Any], ldap_connections: dict[str, Connection]
    ) -> None:
        """Initialization of the class."""
        self.basic_config = basic_config
        self.ldap_connections = ldap_connections
        self._main()

    def _group_search(
        self,
        connection: Connection,
        base_string: str,
        filter_string: str,
        attributes: list[str] = ["*"],
    ) -> Any:
        """Search the configured OU for groups.

        Parameters
        ----------
        connection
            Either the MS AD or OpenLDAP LDAP connection.
        base_string
            The base search string.
        filter_string
            The filter string.
        attributes
            Any attributes.

        Returns
        -------
        LDAP Connection
            The LDAP connection response.

        Examples
        --------
        >>> self._group_search(
            self.ldap_connections["openldap"],
            "ou=Group,dc=example,dc=com",
            "(objectclass=posixGroup)"
        )
        [
            {
                "raw_dn": b"cn=hr,ou=Group,dc=example,dc=com",
                "dn": "cn=hr,ou=Group,dc=example,dc=com",
                "raw_attributes": {
                    "memberUid": [b"johnd"],
                    "gidNumber": [b"123"],
                    "cn": [b"hr"],
                    "objectClass": [b"posixGroup", b"top"],
                    "description": [b"Migrated to AD. Do not update in OpenLDAP"],
                },
                "attributes": {
                    "memberUid": ["johnd"],
                    "gidNumber": 123,
                    "cn": ["hr"],
                    "objectClass": ["posixGroup", "top"],
                    "description": ["Migrated to AD. Do not update in OpenLDAP"],
                },
                "type": "searchResEntry",
            }
        ]
        """
        connection.search(base_string, filter_string, attributes=attributes)
        if connection.result["result"] != 0:
            logger.error(
                "Search failed in _group_search, exiting. "
                f"{connection.result['description']}"
            )
            Utilities.write_monitoring_log(self.basic_config, False, "group_sync")
            sys.exit(1)
        return connection.response

    @staticmethod
    def _determine_user_base(
        config: dict[str, Any],
        server_type: str,
        user_base: Optional[str] = None,
    ) -> str | Any:
        """Figure out what the correct user base should be for future searches.

        Parameters
        ----------
        config
            The specific configuration for this server type.
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        user_base
            The base string for the user.

        Returns
        -------
        str
            The correct user base for the specific server.

        Examples
        --------
        >>> self._determine_user_base(self.basic_config["config"], "ad")
        ou=Company,dc=example,dc=com
        """
        if not user_base:
            return (
                f"{config[f'{server_type}']['schema']['users']}"
                f",{config[f'{server_type}']['schema']['base']}"
            )
        return user_base

    def _user_search(
        self,
        server_type: str,
        user_name: str,
        user_base: Optional[str] = None,
    ) -> Any:
        """Search for a specific user in a given server.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        user_name
            This will either be the sAMAccountName for OpenLDAP or
            the Common Name for MS AD.
        user_base : optional
            The user base.

        Returns
        -------
        LDAP Connection
            The LDAP connection response.

        Examples
        --------
        >>> self._user_search("openldap", "johnd")
        [
            {
                "raw_dn": b"uid=johnd,ou=People,dc=example,dc=com",
                "dn": "uid=johdn,ou=People,dc=example,dc=com",
                "raw_attributes": {
                    "objectClass": [b"person"],
                    "gecos": [b"johnd"],
                },
                "attributes": {
                    "objectClass": ["person"],
                    "gecos": "johnd",
                },
                "type": "searchResEntry",
            }
        ]
        """
        connection: Connection = self.ldap_connections[server_type]
        config: dict[str, Any] = self.basic_config["config"]
        user_base_string = self._determine_user_base(config, server_type, user_base)
        user_filter_string = f"(&(objectclass={config[f'{server_type}']['schema']['objects']['user']['obj_class']})({user_name}))"  # noqa ignore long line
        connection.search(user_base_string, user_filter_string, attributes=["*"])
        return connection.response

    def _modify_group(
        self,
        server_type: str,
        connection: Connection,
        group_dn: str,
        action: str,
        user_list: list[str],
    ) -> None:
        """Make changes to the group.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        connection
            The relevant LDAP server connection.
        group_dn
            The group Distinguished Name to act on.
        action
            What action to take.
            https://ldap3.readthedocs.io/en/latest/operations.html
        user_list
            The list of users to take action on.

        Returns
        -------
        --
            NO RETURN. Modify the relevant group.

        Examples
        --------
        >>> self._modify_group(
            "openldap",
            self.ldap_connections["openldap"],
            "cn=test_group,ou=Group,dc=example,dc=com",
            "MODIFY_DELETE",
            ["johnd"]
        )
        """
        config: dict[str, Any] = self.basic_config["config"]
        group_cn = group_dn.split(",")[0].split("=")[1]
        group_object_name = config[server_type]["schema"]["objects"]["group"]["members"]
        group_modification = {group_object_name: [(action, user_list)]}

        if user_list:
            logger.info(f"{group_cn}: Will {action}: {user_list}")
            connection.modify(group_dn, group_modification)
            if connection.result["result"] != 0:
                self.run_status = False
                logger.error(f"{group_cn}: Failed to execute {action}")
        else:
            logger.debug(f"{group_cn}: Has no users to perform {action}")

    @staticmethod
    def _determine_group_name(group_name_object: str | list[str]) -> Any:
        """Determine the group name to use.

        Parameters
        ----------
        group_name_object
            The group name from the LDAP connection results.

        Returns
        -------
        str
            The correct group name.

        Examples
        --------
        >>> self._determine_group_name("ad-ldap-sync-test")
        ad-ldap-sync-test
        """
        if type(group_name_object) is list:
            # MS AD and OpenLDAP give results in different formats.
            return group_name_object[0]
        return group_name_object

    def _determine_group_id(
        self,
        server_type: str,
        group: dict[str, Any],
        group_name: str,
    ) -> int | Any:
        """Determine the group ID.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        group
            The whole group object from the LDAP connection results.
        group_name
            The group name.

        Returns
        -------
        int
            The correct group ID.
            If there is no group ID found, `-1` will be returned.

        Examples
        --------
        >>> self._determine_group_id(
            "openldap", {"attributes": {"cn": ["test_group"]}}, "test_group"
        )
        -1
        """
        config: dict[str, Any] = self.basic_config["config"]
        if (
            config[server_type]["schema"]["objects"]["group"]["gid_number"]
            in group["attributes"]
        ):
            return group["attributes"][
                config[server_type]["schema"]["objects"]["group"]["gid_number"]
            ]
        else:
            logger.debug(f"No GID for group '{group_name}'")
            return -1

    def _determine_group_members(
        self, server_type: str, group: dict[str, Any]
    ) -> list[str] | Any:
        """Determine the group members.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        group
            The whole group object from the LDAP connection results.

        Returns
        -------
        list[str]
            All members of the group.
            If there are no members found, an empty list will be returned.

        Examples
        --------
        >>> self._determine_group_members("openldap", "test_group")
        {
            "dn": "cn=test_group,ou=Group,dc=example,dc=com",
            "attributes": {
                "memberUid": ["test_group"],
                "gidNumber": 123,
                "cn": ["test_group"],
            },
        }
        ["johnd"]
        """
        config: dict[str, Any] = self.basic_config["config"]
        if (
            config[server_type]["schema"]["objects"]["group"]["members"]
            in group["attributes"]
        ):
            return group["attributes"][
                config[server_type]["schema"]["objects"]["group"]["members"]
            ]
        return []

    def _create_group_dictionary(
        self,
        server_type: str,
        search_results: list[Any],
    ) -> dict[str, Any]:
        """Create the group dictionary.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        search_results
            The group search from the LDAP connection results.

        Returns
        -------
        dict[str, Any]
            A dictionary with all the groups, their ID's and the members of the group.

        Examples
        --------
        >>> self._create_group_dictionary(
            "ad",
            [
                {
                    "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                    "attributes": {
                        "objectClass": ["top", "group"],
                        "cn": "example_group",
                        "member": [
                            "CN=John Doe,OU=User Accounts,DC=example,DC=com",
                            "CN=Jane Doe,OU=User Accounts,DC=example,DC=com",
                        ],
                        "distinguishedName": "CN=test_group,OU=Groups,DC=example,DC=com",
                        "name": "example_group",
                        "sAMAccountName": "example_group",
                        "gidNumber": 1186,
                    },
                }
            ]
        )
        {
            "test_group": {
                "id": 123,
                "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                "names": {
                    "CN=John Doe,OU=User Accounts,DC=example,DC=com",
                    "CN=Jane Doe,OU=User Accounts,DC=example,DC=com",
                },
                "server_type": "ad",
            }
        }

        >>> self._create_group_dictionary(
            "openldap",
            [
                {
                    "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                    "attributes": {
                        "gidNumber": 123,
                        "cn": ["test_group"],
                        "objectClass": ["posixGroup", "top"],
                        "memberUid": ["johnd", "janed"],
                    }
                }
            ]
        )
        {
            "test_group": {
                "id": 123,
                "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                "names": ["johnd", "janed"],
                "server_type": "openldap",
            }
        }
        """
        config: dict[str, Any] = self.basic_config["config"]
        group_dict: dict[str, Any] = {}
        for group in search_results:
            group_name_object = group["attributes"][
                config[server_type]["schema"]["objects"]["group"]["name"]
            ]
            group_name = self._determine_group_name(group_name_object)
            group_id = self._determine_group_id(
                server_type,
                group,
                group_name,
            )
            group_members = self._determine_group_members(server_type, group)
            if server_type == "ad":
                group_members = self._flatten_nested_group(
                    called_groups=[group["dn"]],
                    group_members=group_members,
                )
            group_dict[group_name] = {
                "id": group_id,
                "dn": group["dn"],
                "names": group_members,
                "server_type": server_type,
            }
        return group_dict

    def _flatten_nested_group(
        self,
        called_groups: list[str],
        group_members: list[str],
    ) -> set[str]:
        """Flatten nested groups.

        Parameters
        ----------
        called_groups
            A list of all the groups that have already been called by this method.
        group_members
            A list of all the members in the group to flatten.

        Returns
        -------
        set[str]
            The set of users only from all the nested groups.

        Examples
        --------
        >>> self._flatten_nested_group(
            ["CN=test_group,OU=Linux,OU=Groups,OU=Company,DC=example,DC=com"],
            group_members=[
                "CN=2nd_level_group,OU=Groups,DC=example,DC=com",
                "CN=John Doe,OU=Users,DC=example,DC=com",
            ],
        )
        {'CN=John Doe,OU=Users,DC=example,DC=com'}
        """
        config: dict[str, Any] = self.basic_config["config"]
        return_set: set[str] = set({})
        nested_members: set[str] = set({})
        for ad_object in group_members:
            if self._check_ad_object_type(ad_object, object_type="user"):
                return_set.add(ad_object)
            elif self._check_ad_object_type(ad_object, object_type="group"):
                if ad_object not in called_groups:
                    group_base_string = f"{config['ad']['schema']['base']}"
                    group_filter_string = f"(distinguishedName={ad_object})"
                    attributes = ["member"]
                    ad_search_result = self._group_search(
                        self.ldap_connections["ad"],
                        group_base_string,
                        group_filter_string,
                        attributes,
                    )
                    object_members = ad_search_result[0]["attributes"]["member"]
                    called_groups.extend(ad_object)
                    nested_members = self._flatten_nested_group(
                        called_groups=called_groups,
                        group_members=object_members,
                    )
            else:
                logger.warning("We found an object of unexpected type. " f"{ad_object}")
        return set.union(nested_members, return_set)

    def _check_ad_object_type(
        self,
        ad_object: str,
        object_type: str,
    ) -> bool:
        """Check if the object is a user or a group.

        Parameters
        ----------
        ad_object
            The input object to test against.
        object_type
            The type to test for. Either "user" or "group".

        Returns
        -------
        bool
            True if the ad_object == object_type, False otherwise.

        Examples
        --------
        >>> self._check_ad_object_type(
            "CN=John Doe,OU=Users,DC=example,DC=com", object_type="user"
        )
        True
        """
        connection: Connection = self.ldap_connections["ad"]
        attributes = ["objectClass"]
        base_string = self.basic_config["config"]["ad"]["schema"]["base"]
        filter_string = f"(distinguishedName={ad_object})"
        if filter_string in self.object_lookup_cache:
            response = self.object_lookup_cache[filter_string]
        else:
            connection.search(
                base_string, filter_string, search_scope=SUBTREE, attributes=attributes
            )
            response = connection.response[0]["attributes"]["objectClass"]
            self.object_lookup_cache[filter_string] = response
        if object_type in response:
            return True
        return False

    @staticmethod
    def _build_sync_group_list(
        first_group_dict: dict[str, Any],
        second_group_dict: dict[str, Any],
    ) -> list[str]:
        """Create a list of valid groups to synchronize.

        Parameters
        ----------
        first_group_dict
            Either the MS AD or OpenLDAP group dictionary.
        second_group_dict
            Either the MS AD or OpenLDAP group dictionary.

        Returns
        -------
        list[str]
            List of valid groups to synchronize.

        Examples
        --------
        >>> self._build_sync_group_list(
            {
                "test_group": {
                    "id": 123,
                    "dn": "CN=test_group,OU=Groups,DC=ai",
                    "names": {
                        "CN=John Doe,OU=Users,DC=ai",
                        "CN=Jane Doe,OU=Users,DC=ai",
                    },
                    "server_type": "ad",
                }
            },
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=test_group,ou=Group,dc=ai",
                    "names": ["johnd", "janed"],
                    "server_type": "openldap",
                }
            },
        )
        ['test_group']
        """
        valid_sync_groups: list[str] = []
        for group in first_group_dict:
            if group in second_group_dict:
                if first_group_dict[group]["id"] == second_group_dict[group]["id"]:
                    logger.info(f"{group} exists and IDs match: valid for sync")
                    valid_sync_groups.append(group)
                else:
                    logger.debug(f"{group} exists but GID mismatch")
            else:
                logger.debug(f"{group} only exists in one directory")
        return valid_sync_groups

    def _check_country_control(
        self,
        account_data: dict[str, Any],
        valid_sync_group: str,
    ) -> bool:
        """Check if a user should be in a group based on country control.

        Parameters
        ----------
        account_data
            Dictionary of relevant account data for the user to test against.
        valid_sync_group
            Group to test against.

        Returns
        -------
        bool
            False if this group has country control and the user isn't authorized.
            True in any other case.

        Examples
        --------
        >>> self._check_country_control(
            {"sAMAccountName": "johnd", "country_code": "TW", "account_active": True},
            "test_group",
        )
        False
        """
        country_control: dict[str, list[str]] = self.basic_config["country_control"]
        if country_control:
            if valid_sync_group in country_control:
                if account_data["country_code"] == "":
                    return True
                elif account_data["country_code"] in country_control[valid_sync_group]:
                    return True
                else:
                    logger.debug(
                        f"{valid_sync_group}: Is controlled and user "
                        f"'{account_data['sAMAccountName']}' is not "
                        "in a valid country. User excluded."
                    )
                    return False
        return True

    def _find_user_in_source_dict(
        self,
        source_dict: dict[str, Any],
        destination_member: str,
        valid_sync_group: str,
    ) -> bool:
        """Test if a user is in the source dictionary.
        Parameters
        ----------
        source_dict
            The input dictionary to search against.
        destination_member
            The user to test against.
        valid_sync_group
            Group to test against.

        Returns
        -------
        bool
            True if the user is found in the source dictionary.
            False otherwise.

        Examples
        --------
        >>> self._find_user_in_source_dict(
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                    "names": [],
                    "server_type": "openldap",
                }
            },
            "johnd",
            "test_group",
        )
        False
        """
        found = False
        for source_member in source_dict[valid_sync_group]["names"]:
            account_data = self._lookup_ad_user(
                source_member,
            )
            if (
                destination_member == account_data["sAMAccountName"]
                and account_data["account_active"] is True
            ):
                found = True
        return found

    def _generate_additions(
        self,
        source_dict: dict[str, Any],
        destination_dict: dict[str, Any],
        valid_sync_group: str,
    ) -> list[str]:
        """Generate all the additions for this group.

        Parameters
        ----------
        source_dict
            The input dictionary to search against.
        destination_dict
            The destination dictionary to test against.
        valid_sync_group
            Group to test against.

        Returns
        -------
        list[str]
            A list of additions for this group.

        Examples
        --------
        >>> self._generate_additions(
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                    "names": [],
                    "server_type": "openldap",
                }
            },
            {
                {
                    "id": 123,
                    "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                    "names": {
                        "CN=Jane Doe,OU=Users,DC=example,DC=com",
                        "CN=John Doe,OU=Users,DC=example,DC=com",
                    },
                    "server_type": "ad",
                }
            },
            ["test_group"],
        )
        ["janed", "johnd"]
        """
        additions = []
        for source_member in source_dict[valid_sync_group]["names"]:
            account_data = self._lookup_ad_user(
                source_member,
            )
            if (
                account_data["sAMAccountName"]
                not in destination_dict[valid_sync_group]["names"]
                and account_data["sAMAccountName"] != ""
                and account_data["account_active"] is True
                and self._check_country_control(account_data, valid_sync_group)
            ):
                additions.append(account_data["sAMAccountName"])
        return additions

    def _generate_deletions(
        self,
        destination_dict: dict[str, Any],
        source_dict: dict[str, Any],
        valid_sync_group: str,
    ) -> list[str]:
        """Generate all the deletions for this group.

        Parameters
        ----------
        source_dict
            The input dictionary to search against.
        destination_dict
            The destination dictionary to test against.
        valid_sync_group
            Group to test against.

        Returns
        -------
        list[str]
            A list of deletions for this group.

        Examples
        --------
        >>> self._generate_deletions(
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                    "names": [],
                    "server_type": "openldap",
                }
            },
            {
                {
                    "id": 123,
                    "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                    "names": {
                        "CN=Jane Doe,OU=Users,DC=example,DC=com",
                        "CN=John Doe,OU=Users,DC=example,DC=com",
                    },
                    "server_type": "ad",
                }
            },
            ["test_group"],
        )
        []
        """
        deletions = []
        for destination_member in destination_dict[valid_sync_group]["names"]:
            found = self._find_user_in_source_dict(
                source_dict,
                destination_member,
                valid_sync_group,
            )
            if not found:
                deletions.append(destination_member)
        return deletions

    def _generate_group_operations(
        self,
        source_dict: dict[str, Any],
        destination_dict: dict[str, Any],
        valid_sync_groups: list[str],
    ) -> dict[str, Any]:
        """Generate all the operations for this group.

        Parameters
        ----------
        source_dict
            The input dictionary to search against.
        destination_dict
            The destination dictionary to test against.
        valid_sync_groups
            List of all valid groups to synchronize.

        Returns
        -------
        dict[str, Any]
            A dictionary of all the relevant operations to perform for this group.

        Examples
        --------
        >>> self._generate_group_operations(
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=test_group,ou=Group,dc=example,dc=com",
                    "names": [],
                    "server_type": "openldap",
                }
            },
            {
                {
                    "id": 123,
                    "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                    "names": {
                        "CN=Jane Doe,OU=Users,DC=example,DC=com",
                        "CN=John Doe,OU=Users,DC=example,DC=com",
                    },
                    "server_type": "ad",
                }
            },
            ["test_group"],
        )
        'test_Group': {'additions': [], 'deletions': [], 'override_required': False}
        """
        destination_operations: dict[str, Any] = {}
        for valid_sync_group in valid_sync_groups:
            destination_operations[valid_sync_group] = {}
            destination_operations[valid_sync_group][
                "additions"
            ] = self._generate_additions(
                source_dict,
                destination_dict,
                valid_sync_group,
            )
            destination_operations[valid_sync_group][
                "deletions"
            ] = self._generate_deletions(
                destination_dict,
                source_dict,
                valid_sync_group,
            )
            destination_operations[valid_sync_group][
                "override_required"
            ] = self._check_override_required(
                destination_dict[valid_sync_group]["names"],
                destination_operations[valid_sync_group],
                valid_sync_group,
            )
        return destination_operations

    @staticmethod
    def _determine_change_percent(
        destination_list: list[str], destination_operations: dict[str, Any]
    ) -> dict[str, int]:
        """Determine the relevant change percentages.

        Parameters
        ----------
        destination_list
            The list of users in this group.
        destination_operations
            The list of operations for this group.

        Returns
        -------
        dict[str, int]
            A dictionary of all the relevant change percentages and numbers.

        Examples
        --------
        >>> self._determine_change_percent(
            ["test_user"],
            {
                "test_group": {
                    "additions": [],
                    "deletions": [],
                    "override_required": False,
                }
            },
            "test_group",
        )
        {
            "original_len": 1,
            "deletions_len": 0,
            "additions_len": 0,
            "total_change_size": 0,
            "total_change_percent": 0,
            "deletions_change_percent": 0,
            "additions_change_percent": 0,
        }
        """
        # Ensure we don't divide by zero if there is nothing in the
        # destination list.
        change_data: dict[str, int] = {
            "original_len": max(len(destination_list), 1),
            "deletions_len": len(destination_operations["deletions"]),
            "additions_len": len(destination_operations["additions"]),
        }
        change_data["total_change_size"] = (
            change_data["additions_len"] + change_data["deletions_len"]
        )
        change_data["total_change_percent"] = int(
            abs(change_data["total_change_size"] / change_data["original_len"] * 100)
        )
        change_data["deletions_change_percent"] = int(
            change_data["deletions_len"] / change_data["original_len"] * 100
        )
        change_data["additions_change_percent"] = int(
            change_data["additions_len"] / change_data["original_len"] * 100
        )
        return change_data

    def _check_override_required(
        self,
        destination_list: list[str],
        destination_operations: dict[str, Any],
        group_name: str,
    ) -> bool:
        """Determine if override is required for this group change set.

        Parameters
        ----------
        destination_list
            The list of users in this group.
        destination_operations
            The list of operations for this group.

        Returns
        -------
        bool
            True if override is required for this group change set.
            False otherwise.

        Examples
        --------
        >>> self._check_override_required(
            ["test_user"],
            {
                "test_group": {
                    "additions": [],
                    "deletions": ["johnd"],
                    "override_required": False,
                }
            },
            "test_group",
        )
        False
        """
        config: dict[str, Any] = self.basic_config["config"]
        override_required = False
        change_data = self._determine_change_percent(
            destination_list, destination_operations
        )
        total_change_threshold = config["settings"]["total_change_threshold"]
        deletions_change_threshold = config["settings"]["deletions_change_threshold"]
        additions_change_threshold = config["settings"]["additions_change_threshold"]
        logger.debug(
            f"{group_name}: Original length    -> {change_data['original_len']}"
        )
        logger.debug(
            f"{group_name}: Total change delta -> "
            f"{change_data['total_change_size']} "
            f"({change_data['total_change_percent']}%)"
        )
        logger.debug(
            f"{group_name}: Additions          -> "
            f"{change_data['additions_len']} "
            f"({change_data['additions_change_percent']}%)"
        )
        logger.debug(
            f"{group_name}: Deletions          -> "
            f"{change_data['deletions_len']} "
            f"({change_data['deletions_change_percent']}%)"
        )
        if (
            change_data["total_change_percent"]
            > config["settings"]["total_change_threshold"]
        ):
            logger.debug(
                f"{group_name}: Total change threshold breach. "
                f"Total change percentage {change_data['total_change_percent']}% "
                f"greater than configured threshold {total_change_threshold}%."
            )
            override_required = True
        if (
            change_data["deletions_change_percent"]
            > config["settings"]["deletions_change_threshold"]
        ):
            logger.debug(
                f"{group_name}: Deletion change threshold breach. "
                f"Deletion change percentage "
                f"{change_data['deletions_change_percent']}% "
                f"greater than configured threshold {deletions_change_threshold}%"
            )
            override_required = True
        if (
            change_data["additions_change_percent"]
            > config["settings"]["additions_change_threshold"]
        ):
            logger.debug(
                f"{group_name}: Addition change threshold breach. "
                "Addition change percentage "
                f"{change_data['additions_change_percent']}% "
                f"greater than configured threshold {additions_change_threshold}%"
            )
            override_required = True
        # Must come last, to make sure small groups never require override
        if (
            change_data["original_len"] < config["settings"]["small_group_blind_update"]
            and override_required
        ):
            logger.debug(
                f"{group_name}: Group is below small_group_blind_update "
                f"threshold of {config['settings']['small_group_blind_update']} "
                "so we will proceed anyway."
            )
            override_required = False
        return override_required

    def _lookup_ad_user(
        self,
        ad_user: str,
    ) -> dict[str, Any]:
        """Find a user in MS AD.

        Check if the user is in the cache first to save making external API calls.

        Parameters
        ----------
        ad_user
            The full Distinguished Name of the MS AD user.

        Returns
        -------
        dict[str, Any]
            A dictionary with the relevant user details and `sAMAccountName`
            as the primary key.
            If nothing relevant is found, return with a fixed dictionary of
            know negative values.

        Examples
        --------
        >>> self._lookup_ad_user(CN=Jodn Doe,OU=User Accounts,DC=example,DC=com)
        {
            "sAMAccountName": "johnd",
            "country_code": GB,
            "account_active": False,
        }
        """
        exceptions: dict[str, str] = self.basic_config["exceptions"]
        if not exceptions:
            exceptions = {}
        if ad_user in self.user_lookup_cache:
            return self.user_lookup_cache[ad_user]
        else:
            account_data = self._get_account_data(ad_user)
            if account_data["sAMAccountName"] in exceptions:
                exception_lookup = self._user_search(
                    "openldap",
                    f"uid={exceptions[account_data['sAMAccountName']]}",
                )
                if len(exception_lookup) == 1:
                    account_data["sAMAccountName"] = exceptions[
                        account_data["sAMAccountName"]
                    ]
                    self.user_lookup_cache[ad_user] = account_data
                    return self.user_lookup_cache[ad_user]
                elif not exception_lookup:
                    if exceptions[account_data["sAMAccountName"]] != "NONE":
                        logger.warning(
                            f"{account_data['sAMAccountName']} in exception list, "
                            "but target not in OpenLDAP. Skipping."
                        )
                        self.run_status = False
                else:
                    logger.warning(
                        (
                            f"{account_data['sAMAccountName']} in exception list, "
                            "but target matches multiple objects in OpenLDAP. Skipping."
                        )
                    )
                    self.run_status = False
            else:
                ldap_lookup = self._user_search(
                    "openldap",
                    f"uid={account_data['sAMAccountName']}",
                )
                if len(ldap_lookup) == 1:
                    self.user_lookup_cache[ad_user] = account_data
                    return self.user_lookup_cache[ad_user]
                else:
                    logger.warning(
                        f"{account_data['sAMAccountName']} not in OpenLDAP or more "
                        "than one account found. Skipping."
                    )
                    self.run_status = False
        return {
            "sAMAccountName": "",
            "country_code": None,
            "account_active": False,
        }

    def _get_account_data(
        self,
        ad_user: str,
    ) -> dict[str, Any]:
        """Get account data for the user.

        Parameters
        ----------
        ad_user
            The full Distinguished Name of the MS AD user.

        Returns
        -------
        dict[str, Any]
            A dictionary with the relevant user details.

        Examples
        --------
        >>> self._get_account_data("CN=Test User,OU=Users,DC=example,DC=com")
        CN=Jodn Doe,OU=User Accounts,OU=Company,DC=example,DC=com
        """
        account_data: dict[str, Any] = {
            "sAMAccountName": "",
            "country_code": None,
            "account_active": False,
        }
        cn = ad_user.split(",")[0]
        base = ad_user.split(",", 1)[-1]
        ms_ad_disabled_user = 514
        ms_ad_disabled_user_no_expire = 66050
        try:
            full_output = self._user_search("ad", cn, base)[0]["attributes"]
            if (full_output["userAccountControl"] != ms_ad_disabled_user) and (
                full_output["userAccountControl"] != ms_ad_disabled_user_no_expire
            ):
                account_data["account_active"] = True
            account_data["sAMAccountName"] = full_output["sAMAccountName"].lower()
            account_data["country_code"] = full_output.get("c", None)
            return account_data
        except Exception:
            logger.warning(f"{cn} does not exist in MS AD. Skipping")
            self.run_status = False
            return account_data

    def _process_operations(
        self,
        destination_group_dict: dict[str, Any],
        group_operations: dict[str, Any],
    ) -> None:
        """Process the operations for this group.

        Parameters
        ----------
        destination_group_dict
            Dictionary of all the groups and their users
        group_operations
            The operations to perform.

        Returns
        -------
        --
            NO RETURN. This calls `self._modify_group`.

        Examples
        --------
        >>> self._process_operations(
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=hr,ou=Group,dc=ai",
                    "names": ["janed"],
                    "server_type": "openldap",
                }
            },
            {
                "test_group": {
                    "additions": [],
                    "deletions": ["johnd"],
                    "override_required": False,
                }
            },
        )
        """
        config: dict[str, Any] = self.basic_config["config"]
        for group in group_operations:
            group_base = (
                f"{config['openldap']['schema']['groups']},"
                f"{config['openldap']['schema']['base']}"
            )
            group_dn = f"cn={group},{group_base}"
            process_changes = self._check_process_changes(
                destination_group_dict, group, group_operations
            )
            operations = {"additions": MODIFY_ADD, "deletions": MODIFY_DELETE}
            if process_changes:
                for operation in operations:
                    self._modify_group(
                        "openldap",
                        self.ldap_connections["openldap"],
                        group_dn,
                        operations[operation],
                        group_operations[group][operation],
                    )

    def _check_process_changes(
        self,
        destination_group_dict: dict[str, Any],
        group: str,
        group_operations: dict[str, Any],
    ) -> bool:
        """Check if the operations for this group should be processed or not
        based on the relevant thresholds.

        Parameters
        ----------
        destination_group_dict
            Dictionary of all the groups and their users
        group
            The group to operate on.
        group_operations
            The operations to perform.

        Returns
        -------
        bool
            True if none of the thresholds are breached, else False.

        Examples
        -------
        >>> self._check_process_changes(
            {
                "test_group": {
                    "id": 123,
                    "dn": "cn=hr,ou=Group,dc=ai",
                    "names": ["janed"],
                    "server_type": "openldap",
                }
            },
            "test_group",
            {
                "test_group": {
                    "additions": [],
                    "deletions": ["johnd"],
                    "override_required": False,
                }
            },
        )
        True
        """
        args: ManageArguments = self.basic_config["args"]
        process_changes = False
        if (
            len(group_operations[group]["additions"]) > 0
            or len(group_operations[group]["deletions"]) > 0
        ):
            if group_operations[group]["override_required"]:
                if args.universal_override or group in args.group_override:
                    process_changes = True
                    logger.info(f"{group}: Running in override. Applying all changes.")
                else:
                    logger.warning(
                        f"{group}: Breaches thresholds but override mode not set. "
                        "Consult with owner and run in override."
                    )
                    logger.warning(
                        f"{group}: Current members: "
                        f"{destination_group_dict[group]['names']}"
                    )
                    logger.warning(
                        f"{group}: Proposed additions: "
                        f"{group_operations[group]['additions']}"
                    )
                    logger.warning(
                        f"{group}: Proposed deletions: "
                        f"{group_operations[group]['deletions']}"
                    )
                    self.run_status = False
            else:
                process_changes = True
                logger.info(f"{group}: No override required, proceeding with changes.")
        return process_changes

    def _new_ldap_group(
        self,
        server_type: str,
        group: str,
        openldap_group_dictionary: dict[str, Any],
        ad_group_dictionary: dict[str, Any],
    ) -> None:
        """Add missing group to OpenLDAP.

        Ensure that we update the relevant dictionaries so that we have valid
        synchronization groups on the first run.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        group
            Name of the group we will add.
        openldap_group_dictionary
            Dictionary of all the OpenLDAP groups.
        ad_group_dictionary
            Dictionary of all the MS AD groups.

        Returns
        -------
        --
            NO RETURN. Add any missing groups.

        Examples
        --------
        >>> self._new_ldap_group(
            "openldap",
            "test_group",
            openldap_group_dictionary={},
            ad_group_dictionary={
                "test_group": {
                    "id": 123,
                    "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                    "names": {
                        "CN=John Doe,OU=User Accounts,DC=example,DC=com",
                        "CN=Jane Doe,OU=User Accounts,DC=example,DC=com",
                    },
                    "server_type": "ad",
                }
            },
        )
        """
        group_details = ad_group_dictionary[group]
        base_ou = self.basic_config["config"][server_type]["schema"]["base"]
        group_ou = self.basic_config["config"][server_type]["schema"]["groups"]
        group_att_name = self.basic_config["config"][server_type]["schema"]["objects"][
            "group"
        ]["name"]
        group_att_id = self.basic_config["config"][server_type]["schema"]["objects"][
            "group"
        ]["gid_number"]
        new_group_dn = f"{group_att_name}={group},{group_ou},{base_ou}"
        new_group = copy.deepcopy(
            self.basic_config["config"][server_type]["schema"]["new_group"]["mask"]
        )
        new_group["attributes"][group_att_name] = group
        if group_details.get("id") and group_details["id"] != -1:
            new_group["attributes"][group_att_id] = group_details["id"]
        else:
            new_group["attributes"][group_att_id] = Utilities.get_next_gid_uid_number(
                self.basic_config, self.ldap_connections, "openldap", "group"
            )
            ad_ldap_connection = self.ldap_connections["ad"]
            ad_group_att_gid = self.basic_config["config"]["ad"]["schema"]["objects"][
                "group"
            ]["gid_number"]
            gid_change = {
                ad_group_att_gid: [
                    (MODIFY_REPLACE, [new_group["attributes"][group_att_id]])
                ]
            }
            logger.info(
                f"Setting GID ({new_group['attributes'][group_att_id]}) "
                f"for {group} on MS AD now."
            )
            ad_ldap_connection.modify(group_details.get("dn"), gid_change)
            if ad_ldap_connection.result["result"] != 0:
                logger.error(
                    f"Failed to update GID on MS AD {group}: "
                    f"{ad_ldap_connection.result}"
                )
                self.run_status = False
            else:
                ad_group_dictionary[group]["id"] = new_group["attributes"][group_att_id]

        openldap_ldap_connection = self.ldap_connections[server_type]
        logger.info(
            f"Will create {group} on {server_type} with ID: "
            f"{new_group['attributes'][group_att_id]}."
        )
        openldap_ldap_connection.add(
            new_group_dn, new_group["objectClass"], new_group["attributes"]
        )
        if openldap_ldap_connection.result["result"] != 0:
            logger.error(
                f"Failed to create LDAP account for {group}:"
                f"{openldap_ldap_connection.result}"
            )
            self.run_status = False
        else:
            openldap_group_dictionary[group] = {
                "id": new_group["attributes"][group_att_id],
                "dn": new_group_dn,
                "server_type": "openldap",
                "names": [],
            }

    def _add_missing_openldap_groups(
        self,
        openldap_group_dictionary: dict[str, Any],
        ad_group_dictionary: dict[str, Any],
    ) -> None:
        """Add missing MS AD groups to OpenLDAP.

        Loops over the current MS AD groups and checks if they are in OpenLDAP.

        Parameters
        ----------
        openldap_group_dictionary
            Dictionary of all the OpenLDAP groups.
        ad_group_dictionary
            Dictionary of all the MS AD groups.

        Returns
        -------
        --
            NO RETURN. Create a new group if required.

        Examples
        --------
        >>> self._add_missing_openldap_groups(
            openldap_group_dictionary={},
            ad_group_dictionary={
                "test_group": {
                    "id": 123,
                    "dn": "CN=test_group,OU=Groups,DC=example,DC=com",
                    "names": {
                        "CN=John Doe,OU=User Accounts,DC=example,DC=com",
                        "CN=Jane Doe,OU=User Accounts,DC=example,DC=com",
                    },
                    "server_type": "ad",
                }
            },
        )

        See Also
        --------
        self._new_ldap_group
        """
        for group in ad_group_dictionary:
            if group not in openldap_group_dictionary:
                self._new_ldap_group(
                    "openldap",
                    group,
                    openldap_group_dictionary=openldap_group_dictionary,
                    ad_group_dictionary=ad_group_dictionary,
                )

    def _main(self) -> None:
        """Main method of the class."""
        config: dict[str, Any] = self.basic_config["config"]
        group_base_string = (
            f"{config['ad']['schema']['groups']}," f"{config['ad']['schema']['base']}"
        )
        group_filter_string = f"(objectclass={config['ad']['schema']['objects']['group']['obj_class']})"  # noqa ignore long line
        ad_group_search_result = self._group_search(
            self.ldap_connections["ad"], group_base_string, group_filter_string
        )
        ad_group_dictionary = self._create_group_dictionary(
            "ad", ad_group_search_result
        )
        group_base_string = (
            f"{config['openldap']['schema']['groups']},"
            f"{config['openldap']['schema']['base']}"
        )
        group_filter_string = f"(objectclass={config[f'openldap']['schema']['objects']['group']['obj_class']})"  # noqa ignore long line
        openldap_group_search_result = self._group_search(
            self.ldap_connections["openldap"], group_base_string, group_filter_string
        )
        openldap_group_dictionary = self._create_group_dictionary(
            "openldap",
            openldap_group_search_result,
        )
        self._add_missing_openldap_groups(
            openldap_group_dictionary=openldap_group_dictionary,
            ad_group_dictionary=ad_group_dictionary,
        )
        valid_sync_groups = self._build_sync_group_list(
            ad_group_dictionary, openldap_group_dictionary
        )
        logger.debug(f"Valid sync groups -> {valid_sync_groups}")
        group_operations = self._generate_group_operations(
            ad_group_dictionary,
            openldap_group_dictionary,
            valid_sync_groups,
        )
        self._process_operations(
            openldap_group_dictionary,
            group_operations,
        )
        Utilities.write_monitoring_log(self.basic_config, self.run_status, "group_sync")
