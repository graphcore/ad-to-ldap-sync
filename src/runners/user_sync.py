"""This module is used to synchronize users from MS AD to OpenLDAP."""
import operator
import codecs
import hashlib
import crypt
import secrets
import string
import sys
import copy
import utils.utilities as Utilities
from ldap3 import (
    Connection,
    MODIFY_REPLACE,
    MODIFY_ADD,
)
from loguru import logger
from typing import Any
from unidecode import unidecode


class AdLdapUserSync:
    """Users from a specific OU’s are synchronised (created/modified) between the
    directories.

    - New users will be created in OpenLDAP based on data from MS AD and a standard
      mask.
    - Some user attributes are authoritative in MS AD and copied over to OpenLDAP and
      visa versa. Other attributes may be copied from one field in a directory to
      another field in the same directory.
    - Regardless of group or user synchronisation, users are checked against an
      exception lookup table.

    Parameters
    ----------
    basic_config : dict[str, Any]
        A dictionary containing all the basic configuration settings.
    ldap_connections : dict[str, Connection]
        A dictionary containing all the LDAP connections.
    """

    run_status: bool = True
    """The overall run status of the script. Set to false anytime something goes
    wrong."""
    all_users: dict[str, Any] = {}
    """The main cache for all the users."""

    def __init__(
        self, basic_config: dict[str, Any], ldap_connections: dict[str, Connection]
    ) -> None:
        """Initialization of the class."""
        self.basic_config = basic_config
        self.ldap_connections = ldap_connections
        self._main()

    def _get_user_attributes(self) -> dict[str, list[str]]:
        """Get the relevant user attributes.

        Take care with this particular method as it can be very confusing.
        From the `remote_synced_attrs` configuration entry, `ad` should be populated
        with all `ad` keys and `openldap` values. Visa versa for `openldap`.
        Then add all the "not_synced_attrs" configuration entry, and finally any
        `local_copy_attrs`.

        Returns
        -------
        dict
            A dictionary with all the user attributes to search for.

        Examples
        --------
        >>> self._get_user_attributes()
        {"ad": ["cn", "uidNumber"], "openldap": ["c", "userAccountControl"]}
        """
        user_attributes = {}
        for server_type in self.ldap_connections:
            ldap_connection = self.ldap_connections.copy()
            user_attributes[server_type] = list(
                self.basic_config["config"][server_type]["schema"][
                    "remote_synced_attrs"
                ].keys()
            )
            ldap_connection.pop(server_type)
            for entry in ldap_connection:
                user_attributes[server_type] += list(
                    self.basic_config["config"][entry]["schema"][
                        "remote_synced_attrs"
                    ].values()
                )
            user_attributes[server_type] += self.basic_config["config"][server_type][
                "schema"
            ]["not_synced_attrs"]
            if self.basic_config["config"][server_type]["schema"].get(
                "local_copy_attrs"
            ):
                user_attributes[server_type] += self.basic_config["config"][
                    server_type
                ]["schema"]["local_copy_attrs"].keys()
                user_attributes[server_type] += self.basic_config["config"][
                    server_type
                ]["schema"]["local_copy_attrs"].values()
            user_attributes[server_type] = sorted(
                list(set(user_attributes[server_type]))
            )
            logger.debug(
                f"User attributes for {server_type}: {user_attributes[server_type]}"
            )
        return user_attributes

    def _get_all_users(self) -> None:
        """Get users from both MS AD and OpenLDAP based on a specific OU.

        Returns
        -------
        --
            NO RETURN. Populate the global cache `all_users`.
            A dictionary with all the users `sAMAccountName` as the primary key,
            LDAP servers as secondary keys and then the relevant attributes.

        Examples
        --------
        >>> self._get_all_users()
        {
            "johnd": {
                "ad": {
                    "cn": "John Doe",
                    "uidNumber": 123,
                },
                "openldap": {"uid": "johnd", "cn": "John Doe"},
            }
        }
        """
        user_attributes = self._get_user_attributes()
        primary_keys = {
            "ad": self.basic_config["config"]["ad"]["schema"]["objects"]["user"][
                "name"
            ],
            "openldap": self.basic_config["config"]["openldap"]["schema"]["objects"][
                "user"
            ]["name"],
        }
        for server_type in self.ldap_connections:
            connection: Connection = self.ldap_connections[server_type]
            server_base = self.basic_config["config"][server_type]["schema"]
            for sync_ou in server_base["user_sync_ous"]:
                user_base_string = f"{sync_ou}," f"{server_base['base']}"
                user_filter_string = (
                    f"(objectclass={server_base['objects']['user']['obj_class']})"
                )
                connection.search(
                    user_base_string,
                    user_filter_string,
                    attributes=user_attributes[server_type],
                )
                logger.debug(
                    f"Users in {server_type}/{sync_ou}: {len(connection.response)}"
                )
                for entry in connection.response:
                    _user = "".join(
                        entry["attributes"][primary_keys[server_type]]
                    ).lower()
                    if _user not in self.all_users:
                        self.all_users[_user] = {}
                    # LDAP returns ldap3.utils.ciDict.CaseInsensitiveDict so we
                    # need to convert to normal dict. Not 100% required, but
                    # makes life a little easier during debugging.

                    self.all_users[_user][server_type] = dict(entry["attributes"])
                    for attr in ("uid", "sAMAccountName"):
                        if self.all_users[_user][server_type].get(attr):
                            self.all_users[_user][server_type][attr] = "".join(
                                self.all_users[_user][server_type][attr]
                            ).lower()
                    self.all_users[_user][server_type]["dn"] = entry["dn"]
                    # Simpler to add the 'changes' entry here than to
                    # later check if it exists and create it.
                    self.all_users[_user][server_type]["changes"] = {}

    def _get_next_sambasid(self) -> str:
        """Get the next available SambaSID.

        Do not fill in blanks. As in, if there are entries for 100 and 102,
        101 should be ignored and the next entry should be 103.

        Returns
        -------
        str
            A string containing the next available SambaSID.

        Examples
        --------
        >>> self._get_next_sambasid()
        S-1-2-34-5678901234-5678918346-164430003-1857
        """
        openldap = self.ldap_connections["openldap"]
        sid_prefix = self.basic_config["config"]["openldap"]["schema"]["sid_prefix"]
        sid = self.basic_config["config"]["openldap"]["schema"]["objects"]["user"][
            "sid"
        ]
        base_string = f"{self.basic_config['config']['openldap']['schema']['base']}"
        filter_string = f"({sid}={sid_prefix}*)"
        uid_list = [0]
        openldap.search(
            base_string,
            filter_string,
            attributes=sid,
        )
        for entry in openldap.response:
            if entry["attributes"][sid].replace(sid_prefix, "", 1).isnumeric():
                uid_list.append(
                    int(entry["attributes"][sid].replace(sid_prefix, "", 1))
                )
            else:
                logger.warning(f"Found an unexpected {sid}: {entry}")
        highest_uid_number = max(uid_list)
        return f"{sid_prefix}{highest_uid_number + 1}"

    def _generate_password(self) -> str:
        """Generate a random password per the configured options.

        Returns
        -------
        str
            The first un-encoded password that matches the password requirements.

        Examples
        --------
        >>> self._generate_password()
        6JQMApbY%sQc
        """
        special_chars = self.basic_config["config"]["settings"][
            "special_password_characters"
        ]
        banned_chars = self.basic_config["config"]["settings"]["banned_password_chars"]
        password_length = self.basic_config["config"]["settings"]["password_length"]
        alphabet = string.ascii_letters + string.digits + special_chars
        tries = 1000
        while tries > 0:
            tries -= 1
            password = "".join(secrets.choice(alphabet) for _ in range(password_length))
            if (
                any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in special_chars for c in password)
                and not any(c in banned_chars for c in password)
            ):
                return password
        logger.error("Unable to generate password.")
        Utilities.write_monitoring_log(self.basic_config, False, "group_sync")
        sys.exit(1)

    def _set_random_ldap_password(
        self,
        server_type: str,
        user: str,
        password_types: list[str],
    ) -> str:
        """Adds the encoded password to the changes dictionary for the user.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        user
            The user for which we want to change the password.
        password_type : `["userPassword", "SambaNTPassword"]`
            A list of password types to change. It can be one or more from
            the list.

        Returns
        -------
        str
            The first un-encoded password that matches the password requirements.

        Examples
        --------
        >>> self._set_random_ldap_password("openldap", "johnd", ["sambaNTPassword"])
        6JQMApbY%sQc
        """
        password = self._generate_password()

        for password_type in password_types:
            if password_type == "userPassword":  # nosec B105
                openldap_password = str(
                    "{CRYPT}%s"
                    % crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
                ).encode("utf-8")
                self.all_users[user][server_type]["changes"][
                    "userPassword"  # nosec B105
                ] = openldap_password
            elif password_type == "sambaNTPassword":  # nosec B105
                ad_password_bytes = hashlib.new(  # nosec B324
                    "md4", password.encode("utf-16le")
                ).digest()
                ad_password = (
                    codecs.encode(ad_password_bytes, "hex_codec")
                    .decode("utf-8")
                    .upper()
                )
                self.all_users[user][server_type]["changes"][
                    "sambaNTPassword"
                ] = ad_password
        return password

    def _update_ldap_account(self, user: str) -> None:
        """Updates all the relevant details for an existing OpenLDAP account.

        Parameters
        ----------
        user
            The name of the user to create.

        Returns
        -------
        --
            NO RETURN. Update the `all_users` cache with the changes for this user.

        Examples
        --------
        >>> self._update_ldap_account("johnd")
        {'gecos': [('MODIFY_REPLACE', ['johnd'])]}
        """
        user_data = self.all_users[user]
        for server_type in user_data:
            changes = self.all_users[user][server_type]["changes"]
            if changes:
                for change in dict(changes):
                    if self.all_users[user][server_type]["changes"][change]:
                        changes[change] = [(MODIFY_REPLACE, [changes[change]])]
                logger.info(
                    "Will apply the following change(s) for "
                    f"{user} on {server_type}: {changes}"
                )
                self.ldap_connections[server_type].modify(
                    user_data[server_type]["dn"], changes
                )
                if self.ldap_connections[server_type].result["result"] != 0:
                    logger.error(
                        f"Failed to apply change(s) for {user}:"
                        f"{self.ldap_connections[server_type].result['description']}"
                    )
                    self.run_status = False

    def _add_class_to_ldap_account(
        self,
        server_type: str,
        user: str,
        ldap_object_class: str,
    ) -> None:
        """Add any missing objectClass and relevant attribute to an existing LDAP
        account which doesn't have it.

        For details about the Samba SAM Account Control Block Flags, see:
            https://www.samba.org/samba/docs/old/Samba3-HOWTO/passdb.html#TOSHARG-acctflags

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        user
            The name of the user to work on.
        ldap_object_class
            String representing an LDAP class to add to user object.

        Returns
        -------
        --
            NO RETURN. Update the `all_users` cache with the new data for this user.

        Examples
        --------
        >>> self._add_class_to_ldap_account("openldap", "johnd", "top")
        {"objectClass": [(MODIFY_ADD, ["ldapPublicKey"])]}
        """
        base_ou = self.basic_config["config"][server_type]["schema"]["base"]
        user_ou = self.basic_config["config"][server_type]["schema"]["users"]
        user_att_name = self.basic_config["config"][server_type]["schema"]["objects"][
            "user"
        ]["name"]
        user_dn = f"{user_att_name}={user},{user_ou},{base_ou}"

        if ldap_object_class == "sambaSamAccount":
            new_samba_sid = self._get_next_sambasid()
            self._set_random_ldap_password("openldap", user, ["sambaNTPassword"])
            operation = {
                "sambaSid": [(MODIFY_ADD, new_samba_sid)],
                "objectClass": [(MODIFY_ADD, ["sambaSamAccount"])],
            }
        else:
            operation = {
                "objectClass": [(MODIFY_ADD, [ldap_object_class])],
            }

        logger.info(
            f"Will add '{ldap_object_class}' class for {operation} for "
            f"{user} on {server_type}"
        )
        self.ldap_connections[server_type].modify(user_dn, operation)
        if self.ldap_connections[server_type].result["result"] == 0:
            logger.info(f"Succeeded adding '{ldap_object_class}' class for {user}")
        else:
            logger.error(
                f"Failed to add '{ldap_object_class}' class for {user} on {server_type}"
                f": {self.ldap_connections[server_type].result['description']}"
            )
            self.run_status = False

    def _new_ldap_account(self, server_type: str, user: str) -> None:
        """Set all the relevant details for a new OpenLDAP account.

        Parameters
        ----------
        server_type : `ad`, `openldap`
            This maps to the config section of the required server.
        user
            The name of the user to create.

        Returns
        -------
        --
            NO RETURN. Update the `all_users` cache with this new user.

        Examples
        --------
        >>> self._new_ldap_account("openldap", "johnd")
        {"uid": "johnd", "changes": {}}
        """
        base_ou = self.basic_config["config"][server_type]["schema"]["base"]
        user_ou = self.basic_config["config"][server_type]["schema"]["users"]
        user_att_name = self.basic_config["config"][server_type]["schema"]["objects"][
            "user"
        ]["name"]
        new_user_dn = f"{user_att_name}={user},{user_ou},{base_ou}"
        new_user = copy.deepcopy(
            self.basic_config["config"][server_type]["schema"]["new_user"]["mask"]
        )
        new_user["attributes"]["uid"] = new_user["attributes"]["cn"] = user
        new_user["attributes"]["sambaSID"] = self._get_next_sambasid()
        new_user["attributes"]["homeDirectory"] = f"/home/{user}"
        new_user["attributes"]["uidNumber"] = Utilities.get_next_gid_uid_number(
            self.basic_config, self.ldap_connections, "openldap", "user"
        )
        ldap_connection = self.ldap_connections[server_type]

        logger.info(f"Will create {user} on {server_type}.")
        ldap_connection.add(
            new_user_dn, new_user["objectClass"], new_user["attributes"]
        )
        if ldap_connection.result["result"] == 0:
            self.all_users[user][server_type] = new_user["attributes"]
            self.all_users[user][server_type]["dn"] = new_user_dn
            self.all_users[user][server_type]["changes"] = {}
            self._set_random_ldap_password(
                "openldap", user, ["userPassword", "sambaNTPassword"]
            )
        else:
            logger.error(
                f"Failed to create LDAP account for {user}:" f"{ldap_connection.result}"
            )
            self.run_status = False

    def _check_change(self, user: str, operation: Any, mask: str) -> None:
        """Check the user status based on their attributes and amend as appropriate.

        Also change their password if there where changes.

        Parameters
        ----------
        user
            The user on which to act.
        operation : `operator.ne`, `operator.eq`
            The specific operator to use for this change check, from the operator class.
        mask : `enable_user_mask`, `disable_user_mask`
            The specific mask to be applied.

        Returns
        -------
        --
            NO RETURN. Update the user in the `all_users` cache per the required mask
            in the `changes` dictionary and reset the password.

        Examples
        --------
        >>> self._check_change("johnd", operator.eq, "enable_user_mask")
        {
            "loginShell": "/sbin/nologin",
            "sambaAcctFlags": "[DU         ]",
            "sshPublicKey": '[b"ecdsa-sha2-nistp256 abc123 ldap-disable@key"]',
        }
        """
        changed = False
        openldap_schema = self.basic_config["config"]["openldap"]["schema"]
        for attr in openldap_schema["enable_user_mask"]:
            if operation(
                self.all_users[user]["openldap"][attr],
                openldap_schema["disable_user_mask"][attr],
            ):
                self.all_users[user]["openldap"]["changes"][attr] = openldap_schema[
                    mask
                ][attr]
                logger.debug(f"Setting {user}/{attr} to: {openldap_schema[mask][attr]}")
                changed = True
        if changed:
            logger.info(f"Applying state change of {user} per {mask}.")
            self._set_random_ldap_password(
                "openldap", user, ["userPassword", "sambaNTPassword"]
            )

    def _check_user_enable_disable(self) -> None:
        """Check if the user is enabled or disabled and act acordingly.

        Depending on the state of the user, other methods will be called to take action.

        Examples
        --------
        >>> self._check_user_enable_disable()

        See Also
        --------
        self._add_class_to_ldap_account
        self._check_change
        self._new_ldap_account
        """
        ms_ad_active_account_ids = self.basic_config["config"]["settings"][
            "ms_ad_active_account_ids"
        ]
        for user in self.all_users:
            if self.all_users[user].get("openldap") and self.all_users[user].get("ad"):
                for ldap_object_class in self.basic_config["config"]["openldap"][
                    "schema"
                ]["new_user"]["mask"]["objectClass"]:
                    if (
                        ldap_object_class
                        not in self.all_users[user]["openldap"]["objectClass"]
                    ):
                        self._add_class_to_ldap_account(
                            "openldap", user, ldap_object_class
                        )
                if (
                    self.all_users[user]["ad"].get("userAccountControl")
                    in ms_ad_active_account_ids
                ):
                    self._check_change(user, operator.eq, "enable_user_mask")
                else:
                    self._check_change(user, operator.ne, "disable_user_mask")
            elif self.all_users[user].get("ad") and not self.all_users[user].get(
                "openldap"
            ):
                if self.all_users[user]["ad"].get("uid") != "NONE":
                    self._new_ldap_account("openldap", user)
            elif self.all_users[user].get("openldap") and not self.all_users[user].get(
                "ad"
            ):
                logger.debug(
                    f"{user} only has an OpenLDAP account. MS AD account missing."
                )

    def _convert_lists_to_strings(self) -> None:
        """Convert all attributes that have lists as values to strings.

        OpenLDAP results are lists and MS AD results are just strings,
        unless the results are empty and then MS AD returns an empty list.
        This normalizes to strings so that we can do direct comparisons.

        In addition, OpenLDAP stores the SSH keys as byte encoded strings,
        even if you send it normal strings. We thus need to decode bytes
        to strings for the comparison later on.

        Lastly, we have no code to handly any list longer than one entry, thus
        we hard exit to avoid potential issues down stream.

        Returns
        -------
        --
            NO RETURN. Update the user in the `all_users` cache.

        Examples
        --------
        >>> self._convert_lists_to_strings()
        """
        for user in self.all_users:
            for server_type in self.all_users[user]:
                for attribute in self.all_users[user][server_type]:
                    if isinstance(self.all_users[user][server_type][attribute], list):
                        if len(self.all_users[user][server_type][attribute]) < 2:
                            if len(self.all_users[user][server_type][attribute]) > 0:
                                if isinstance(
                                    self.all_users[user][server_type][attribute][0],
                                    bytes,
                                ):
                                    self.all_users[user][server_type][
                                        attribute
                                    ] = "".join(
                                        self.all_users[user][server_type][attribute][
                                            0
                                        ].decode()
                                    )
                            self.all_users[user][server_type][attribute] = "".join(
                                (self.all_users[user][server_type][attribute])
                            )
                        elif attribute != "objectClass":
                            logger.error(
                                "Found array with more than one entry in the "
                                f"following user: {user}"
                            )
                            Utilities.write_monitoring_log(
                                self.basic_config, False, "group_sync"
                            )
                            sys.exit(1)

    def _build_attr_changes(
        self,
        source_server_type: str,
        destination_server_type: str,
        attr_type: str,
    ) -> None:
        """Build the changes for all the relevant attributes.

        This is slightly complicated in that there are both local and
        remotely synchronized attributes.
        In addition, we have both OpenLDAP and MS AD servers.
        Then there is the issue of checking against any local changes before
        making remote changes.

        Parameters
        ----------
        source_server_type : `ad`, `openldap`
            The source server.
        destination_server_type : `ad`, `openldap`
            The destination server.
        attr_type : `local_copy_attrs`, `remote_copy_attrs`
            The type of attribute synchronization we are doing.

        Returns
        -------
        --
            NO RETURN. Update the user in the `all_users` cache with the relevant
            attribute changes.

        Examples
        --------
        >>> self._build_attr_changes(source_server_type="openldap",
            destination_server_type="ad", attr_type="remote_synced_attrs",)
        {'gecos': 'johnd'}

        Warnings
        --------
        If there are already changes present, first check against them as the new
        authoritative source, instead of checking against the original authoritative
        source.
        """
        synced_attrs = self.basic_config["config"][source_server_type]["schema"].get(
            attr_type
        )
        if synced_attrs:
            for user, user_data in self.all_users.items():
                ad_data = user_data.get("ad", {})
                uid = ad_data.get("uid", "")
                if uid == "NONE":
                    logger.info(
                        f"User '{user}' has its UID set to 'NONE' in the exception "
                        "file. User not synchronized. Investigation required."
                    )
                    continue
                if user_data.get(destination_server_type) and user_data.get(
                    source_server_type
                ):
                    for attr in synced_attrs:
                        source_changes = user_data[source_server_type]["changes"]
                        destinations_changes = user_data[destination_server_type][
                            "changes"
                        ]
                        if source_changes:
                            # Check here for new authoritative source.
                            if attr in source_changes:
                                destinations_changes[
                                    synced_attrs[attr]
                                ] = source_changes[attr]
                            else:
                                if return_value := self._attr_ascii_compare(
                                    user,
                                    source_server_type,
                                    attr,
                                    destination_server_type,
                                    synced_attrs,
                                ):
                                    destinations_changes[
                                        synced_attrs[attr]
                                    ] = return_value
                        else:
                            if (
                                return_value := self._attr_ascii_compare(
                                    user,
                                    source_server_type,
                                    attr,
                                    destination_server_type,
                                    synced_attrs,
                                )
                            ) is not None:
                                destinations_changes[synced_attrs[attr]] = return_value

    def _attr_ascii_compare(
        self,
        user: str,
        source_server_type: str,
        attr: str,
        destination_server_type: str,
        synced_attrs: dict[Any, Any],
    ) -> Any:
        """
        Compare attributes.

        Our current schema in OpenLDAP only supports IA5String
        (https://ldapwiki.com/wiki/IA5String) for some specific fields (ex: gecos).
        This encoding is essentially just ASCII and does not support UTF-8.
        In MS AD we have users with UTF-8 characters. As such, we have to decode those
        both for testing if there is a change and for assigning the value to OpenLDAP.

        Parameters
        ----------
        user
            The user on which to operate on.
        source_server_type : `ad`, `openldap`
            The source server.
        attr
            The attribute to operate on.
        destination_server_type : `ad`, `openldap`
            The destination server.
        synced_attrs
            A dictionary of all the attributes that are currently being synchronized.

        Returns
        -------
        NoneType
            If there are no changes or the source data field is an empty string.
        str
            Return the source data if there is a change in either the original
            (potential) UTF-8, or ASCII to comply with the current OpenLDAP schema.

        Examples
        --------
        >>> self._attr_ascii_compare(
            "johnd",
            "openldap",
            "unixHomeDirectory",
            "ad",
            "{'uid': 'uid', 'homeDirectory': 'unixHomeDirectory'}",
        )
        /bin/bash
        """
        if self.all_users[user][source_server_type][attr] == "":
            return None
        if destination_server_type == "openldap":
            if isinstance(self.all_users[user][source_server_type][attr], str):
                if not (
                    unidecode(self.all_users[user][source_server_type][attr])
                    == self.all_users[user][destination_server_type][synced_attrs[attr]]
                ):
                    return unidecode(self.all_users[user][source_server_type][attr])
                else:
                    return None
        if not (
            self.all_users[user][source_server_type][attr]
            == self.all_users[user][destination_server_type][synced_attrs[attr]]
        ):
            return self.all_users[user][source_server_type][attr]
        return None

    def _main(self) -> None:
        """Main function of the class."""
        self._get_all_users()

        self._convert_lists_to_strings()
        Utilities.user_exception_lookup(self.basic_config, self.all_users)
        self._check_user_enable_disable()

        self._build_attr_changes(
            source_server_type="ad",
            destination_server_type="ad",
            attr_type="local_copy_attrs",
        )

        self._build_attr_changes(
            source_server_type="ad",
            destination_server_type="openldap",
            attr_type="remote_synced_attrs",
        )

        self._build_attr_changes(
            source_server_type="openldap",
            destination_server_type="openldap",
            attr_type="local_copy_attrs",
        )

        self._build_attr_changes(
            source_server_type="openldap",
            destination_server_type="ad",
            attr_type="remote_synced_attrs",
        )
        for user in self.all_users:
            self._update_ldap_account(user)

        Utilities.write_monitoring_log(self.basic_config, self.run_status, "user_sync")
