"""This module is used to set up all the LDAP connections."""
import ssl
import sys
import utils.utilities as Utilities
from loguru import logger
from typing import Any
from ldap3 import Server, Connection, Tls, core
from utils.ldap_wrapper import NoOp, LdapWrapper

CONNECTION_WRAPPER_REFERENCE = {"noop": NoOp, "prod": LdapWrapper}


class LdapConnections:
    """This class is used to set up all the LDAP connections."""

    @staticmethod
    def _create_tls_object(
        basic_config: dict[str, Any], server_type: str
    ) -> core.tls.Tls:
        """Create the TLS object.

        Parameters
        ----------
        basic_config :
            The basic configuration as per BasicConfig.
        server_type :
            Either "ad" for MS AD or "openldap" for OpenLDAP.
            This maps to the config section of the required server.
        runner :
            The runner this was called from. This will write a monitoring log file for
            that runner.

        Returns
        -------
        TLS object
            https://ldap3.readthedocs.io/en/latest/ssltls.html

        Raises
        ------
        Exception
            Any exception should: notify the user, exit with failure.
        """
        server_config: dict[str, Any] = basic_config["config"][server_type]
        runner = basic_config["args"].op_type
        ca_certs_file = server_config["ssl"].get("ca_certs_file", None)
        try:
            return Tls(
                validate=getattr(ssl, server_config["ssl"]["validate"]),
                version=getattr(ssl, server_config["ssl"]["version"]),
                ciphers="ALL",
                ca_certs_file=ca_certs_file,
            )
        except Exception as exc:
            logger.error("Unable to create OpenLDAP TLS object:")
            logger.error(exc)
            Utilities.write_monitoring_log(basic_config, False, runner)
            sys.exit(1)

    def _create_ldap_server_object(
        self,
        basic_config: dict[str, Any],
        tls_configuration: core.tls.Tls,
        server_type: str,
    ) -> core.server.Server:
        """Create the LDAP server object.

        Parameters
        ----------
        basic_config :
            The basic configuration as per BasicConfig
        tls_configuration :
            https://ldap3.readthedocs.io/en/latest/ssltls.html
        server_type :
            Either "ad" for MS AD or "openldap" for OpenLDAP.
            This maps to the config section of the required server.
        runner :
            The runner this was called from. This will write a monitoring log file for
            that runner.

        Returns
        -------
        TLS object
            https://ldap3.readthedocs.io/en/latest/server.html

        Raises
        ------
        Exception
            Any exception should: notify the user, exit with failure.
        """
        server_config: dict[str, Any] = basic_config["config"][server_type]
        runner = basic_config["args"].op_type
        try:
            return Server(
                server_config["server"],
                port=server_config["port"],
                use_ssl=server_config["ssl"]["enabled"],
                tls=tls_configuration,
                get_info=server_config["get_info"],
            )
        except Exception as exc:
            logger.error("Unable to create OpenLDAP server object:")
            logger.error(exc)
            Utilities.write_monitoring_log(basic_config, False, runner)
            sys.exit(1)

    def _create_ldap_connection_object(
        self,
        basic_config: dict[str, Any],
        ldap_server_object: core.server.Server,
        server_type: str,
    ) -> core.connection.Connection:
        """Create the LDAP connection object.

        Parameters
        ----------
        basic_config :
            The basic configuration as per BasicConfig
        ldap_server_object :
            https://ldap3.readthedocs.io/en/latest/server.html
        server_type :
            Either "ad" for MS AD or "openldap" for OpenLDAP.
            This maps to the config section of the required server.
        runner :
            The runner this was called from. This will write a monitoring log file for
            that runner.

        Returns
        -------
        LDAP Connection object
            https://ldap3.readthedocs.io/en/latest/connection.html

        Raises
        ------
        Exception
            Any exception should: notify the user, exit with failure.
        """
        server_config: dict[str, Any] = basic_config["config"][server_type]
        runner = basic_config["args"].op_type
        try:
            return Connection(
                ldap_server_object,
                user=server_config["bind_user"],
                password=server_config["bind_pass"],
            )
        except Exception as exc:
            logger.error("Unable to create OpenLDAP connection object:")
            logger.error(exc)
            Utilities.write_monitoring_log(basic_config, False, runner)
            sys.exit(1)

    def _bind_to_ldap(
        self, basic_config: dict[str, Any], server_type: str
    ) -> Connection:
        """Bind to the relevant LDAP server.

        Parameters
        ----------
        basic_config :
            The basic configuration as per BasicConfig
        server_type :
            Either "ad" for MS AD or "openldap" for OpenLDAP.
            This maps to the config section of the required server.
        runner :
            The runner this was called from. This will write a monitoring log file for
            that runner.

        Returns
        -------
        LDAP authenticated connection.
            https://ldap3.readthedocs.io/en/latest/bind.html

        Raises
        ------
        Exception
            Any exception should: notify the user, exit with failure.
        """
        tls_object = self._create_tls_object(basic_config, server_type)
        ldap_server_object = self._create_ldap_server_object(
            basic_config, tls_object, server_type
        )
        ldap_connection_object = self._create_ldap_connection_object(
            basic_config, ldap_server_object, server_type
        )
        runner = basic_config["args"].op_type
        try:
            ldap_connection_object.bind()
            return CONNECTION_WRAPPER_REFERENCE[basic_config["args"].environment](
                ldap_connection_object,
                basic_config,
            )
        except Exception as exc:
            logger.error("Unable to bind:")
            logger.error(exc)
            Utilities.write_monitoring_log(basic_config, False, runner)
            sys.exit(1)

    def setup_ldap_connections(
        self, basic_config: dict[str, Any]
    ) -> dict[str, Connection]:
        """Main function of the class."""
        ad_connection = self._bind_to_ldap(basic_config, "ad")
        openldap_connection = self._bind_to_ldap(basic_config, "openldap")
        if not (
            ad_connection.result["result"] == openldap_connection.result["result"] == 0
        ):
            logger.error("One or more Ldap connections failed")
            logger.error(f"OpenLDAP: {openldap_connection.result}")
            logger.error(f"Active Directory: {ad_connection.result}")
            Utilities.write_monitoring_log(basic_config, False, "user_sync")
            sys.exit(1)
        else:
            return {
                "openldap": openldap_connection,
                "ad": ad_connection,
            }
