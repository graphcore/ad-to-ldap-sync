"""This module is used to override some LDAP3 methods."""
import copy
import sys
import json
from loguru import logger
from typing import Any
from ldap3 import Connection, SUBTREE, DEREF_ALWAYS
from datetime import datetime


class LdapInterface:
    """LDAP Interface class.

    Acts as the default implementation.
    """

    def __init__(
        self, ldap_connection: Connection, basic_config: dict[str, Any]
    ) -> None:
        """Initialization of the class."""
        self.basic_config = basic_config
        self.manifest_path: str = basic_config["config"]["settings"]["manifest_path"]
        self.ldap_connection: Connection = (
            ldap_connection  # This is an active bound connection!
        )

    @property  # pragma: no cover
    def response(self) -> Any:
        """Setting response."""
        return self.ldap_connection.response

    @property  # pragma: no cover
    def result(self) -> Any:
        """Setting result."""
        return self.ldap_connection.result

    def unbind(self, controls: Any = None) -> None:
        """As specified in RFC4511 the Unbind operation must be tought as the
        "disconnect" operation. It’s name (and that of its Bind counterpart) is for
        historical reason."""
        raise NotImplementedError

    def add(
        self,
        dn: str,
        object_class: str | None = None,
        attributes: dict[str, Any] | None = None,
        controls: Any = None,
    ) -> None:
        """The Add operation allows a client to request the addition of an entry into
        the LDAP directory. The Add operation is used only for new entries, that is the
        dn must reference a non-existent object, but the parent objects must exist. For
        example if you try to add an entry with dn cn=user1,ou=users,o=company the
        company and users containers must already be present in the directory but the
        user1 object must not exist.
        """
        raise NotImplementedError

    def delete(self, dn: str, controls: Any = None) -> None:
        """The Delete operation allows a client to request the removal of an entry from
        the LDAP directory.
        """
        raise NotImplementedError

    def modify(self, dn: str, changes: dict[str, Any], controls: Any = None) -> None:
        """The Modify operation allows a client to request the modification of an entry
        already present in the LDAP directory.
        """
        raise NotImplementedError

    def modify_dn(
        self,
        dn: str,
        relative_dn: str,
        delete_old_dn: bool = True,
        new_superior: str | None = None,
        controls: Any = None,
    ) -> None:
        """The ModifyDN operation allows a client to change the Relative Distinguished
        Name (RDN) of an entry or to move an entry in the LDAP directory.
        """
        raise NotImplementedError

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: Any = SUBTREE,
        dereference_aliases: Any = DEREF_ALWAYS,
        attributes: Any = None,
        size_limit: int = 0,
        time_limit: int = 0,
        types_only: bool = False,
        get_operational_attributes: bool = False,
        controls: Any = None,
        paged_size: int | None = None,
        paged_criticality: bool = False,
        paged_cookie: str | None = None,
    ) -> None:
        """The Search operation is used to request a server to return, subject to access
        controls and other restrictions, a set of entries matching a search filter. This
        can be used to read attributes from a single entry, from entries immediately
        subordinate to a particular entry, or from a whole subtree of entries.
        """
        raise NotImplementedError

    def compare(
        self, dn: str, attribute: str, value: str, controls: Any = None
    ) -> None:
        """The Compare operation allows a client to request the comparison of an entry
        attribute against a specific value.
        """
        raise NotImplementedError

    def abandon(self, message_id: Any, controls: Any = None) -> None:
        """The use of the Abandon operation is very limited. Its intended function is
        to allow a client to request a server to give up an uncompleted operation.
        Since there is no response from the server the client cannot tell the difference
        between a successfully abandoned operation and a completed operation. The Bind,
        Unbind and the Abandon operations cannot be abandoned.
        """
        raise NotImplementedError

    def extended(
        self,
        request_name: str,
        request_value: str | None = None,
        controls: Any = None,
        no_encode: bool | None = None,
    ) -> None:
        """The Extended operation allows a client to request an operation that may not
        be defined in the current RFCs but is available on the server.
        """
        raise NotImplementedError

    def write_manifest(self, manifest_data: dict[str, Any]) -> None:
        """Write out to the manifest.

        The SSH keys are bytes, so we have to convert them first.
        """
        try:
            with open(self.manifest_path, "a") as f:
                f.write(f"{json.dumps(str(manifest_data))}\n")
        except OSError as exc:
            logger.error("Unable to open file:")
            logger.error(exc)
            sys.exit(1)


class LdapWrapper(LdapInterface):
    """This class is used to override some LDAP3 methods."""

    def unbind(self, controls: Any = None) -> None:
        """As specified in RFC4511 the Unbind operation must be tought as the
        "disconnect" operation. It’s name (and that of its Bind counterpart) is for
        historical reason."""
        kwargs = copy.copy(locals())
        kwargs.pop("self")
        self.ldap_connection.unbind(**kwargs)

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: Any = SUBTREE,
        dereference_aliases: Any = DEREF_ALWAYS,
        attributes: Any = None,
        size_limit: int = 0,
        time_limit: int = 0,
        types_only: bool = False,
        get_operational_attributes: bool = False,
        controls: Any = None,
        paged_size: int | None = None,
        paged_criticality: bool = False,
        paged_cookie: str | None = None,
    ) -> None:
        """The Search operation is used to request a server to return, subject to access
        controls and other restrictions, a set of entries matching a search filter. This
        can be used to read attributes from a single entry, from entries immediately
        subordinate to a particular entry, or from a whole subtree of entries.
        """
        kwargs = copy.copy(locals())
        kwargs.pop("self")
        self.ldap_connection.search(**kwargs)

    def add(
        self,
        dn: str,
        object_class: str | None = None,
        attributes: dict[str, Any] | None = None,
        controls: Any = None,
    ) -> None:
        """The Add operation allows a client to request the addition of an entry into
        the LDAP directory. The Add operation is used only for new entries, that is the
        dn must reference a non-existent object, but the parent objects must exist. For
        example if you try to add an entry with dn cn=user1,ou=users,o=company the
        company and users containers must already be present in the directory but the
        user1 object must not exist.
        """
        kwargs = copy.copy(locals())
        kwargs.pop("self")
        self.ldap_connection.add(**kwargs)
        self.write_manifest(
            {
                "date": str(datetime.now()),
                "add": [dn, object_class, attributes],
                "result": self.ldap_connection.result,
            }
        )

    def modify(self, dn: str, changes: dict[str, Any], controls: Any = None) -> Any:
        """The Modify operation allows a client to request the modification of an entry
        already present in the LDAP directory.
        """
        kwargs = copy.copy(locals())
        kwargs.pop("self")
        self.ldap_connection.modify(**kwargs)
        self.write_manifest(
            {
                "date": str(datetime.now()),
                "modify": [dn, changes],
                "result": self.ldap_connection.result,
            }
        )


class NoOp(LdapInterface):
    """No-operation class for the LDAP connection."""

    def __init__(
        self, ldap_connection: Connection, basic_config: dict[str, Any]
    ) -> None:  # pragma: no cover
        """Initialization of the class."""
        self._response: dict[str, Any] | None = getattr(
            ldap_connection, "response", None
        )
        self._result: dict[str, Any] | None = getattr(ldap_connection, "result", None)
        super().__init__(ldap_connection, basic_config)

    @property
    def response(self) -> Any:
        """Setting response."""
        return self._response

    @property
    def result(self) -> Any:
        """Setting result."""
        return self._result

    def add(
        self,
        dn: str,
        object_class: str | None = None,
        attributes: dict[str, Any] | None = None,
        controls: Any = None,
    ) -> None:
        """The Add operation allows a client to request the addition of an entry into
        the LDAP directory. The Add operation is used only for new entries, that is the
        dn must reference a non-existent object, but the parent objects must exist. For
        example if you try to add an entry with dn cn=user1,ou=users,o=company the
        company and users containers must already be present in the directory but the
        user1 object must not exist.
        """
        self._response = None
        self._result = {
            "result": 0,
            "description": "success",
            "dn": "",
            "message": "",
            "referrals": None,
            "type": "addResponse",
        }

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: Any = SUBTREE,
        dereference_aliases: Any = DEREF_ALWAYS,
        attributes: Any = None,
        size_limit: int = 0,
        time_limit: int = 0,
        types_only: bool = False,
        get_operational_attributes: bool = False,
        controls: Any = None,
        paged_size: int | None = None,
        paged_criticality: bool = False,
        paged_cookie: str | None = None,
    ) -> Any:
        """The Search operation is used to request a server to return, subject to access
        controls and other restrictions, a set of entries matching a search filter. This
        can be used to read attributes from a single entry, from entries immediately
        subordinate to a particular entry, or from a whole subtree of entries.
        """
        kwargs = copy.copy(locals())
        kwargs.pop("self")
        self.ldap_connection.search(**kwargs)
        self._response = self.ldap_connection.response
        self._result = self.ldap_connection.result

    def modify(self, dn: str, changes: dict[str, Any], controls: Any = None) -> Any:
        """The Modify operation allows a client to request the modification of an entry
        already present in the LDAP directory.
        """
        self._response = None
        self._result = {
            "result": 0,
            "description": "success",
            "dn": "",
            "message": "",
            "referrals": None,
            "type": "modifyResponse",
        }
