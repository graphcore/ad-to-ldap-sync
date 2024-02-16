# type: ignore
import logging
import time
from ldap3 import Server, Connection
from unittest.mock import patch
from src.utils.basic_config import BasicConfig
from src.utils.manage_argument_parser import ManageParser
from src.utils.ldap_connections import LdapConnections

# from src.runners.user_sync import AdLdapUserSync

logger = logging.getLogger()
with patch(
    "sys.argv",
    ". user_sync --conf config/config.yaml --exc config/exceptions.yaml --count config/country_control.yaml --no --console error ".split(),  # noqa ignore long line
):
    basic_config = BasicConfig().create_basic_config(ManageParser().parse_cli_args())


class TestMain:
    """
    !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!
              DO NOT RUN IN UNIVERSAL OVERRIDE WITHOUT THE PATCH
    !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!  !!!

    Patch 'XXX' to return only the test users when working
    with universal override.

    Else universal override will apply changes to users we may not want to
    change at present as we are working against the production servers.
    """

    def setup_class(self):
        # Establish the connection
        ldap_connections = LdapConnections().setup_ldap_connections(basic_config)
        max_timeout = 10
        start_time = time.time()
        ldap_server_object = Server("OpenLDAP-int-test", port=1389, get_info="ALL")
        ldap_connection_object = Connection(
            ldap_server_object,
            user="cn=admin,dc=example,dc=org",
            password="adminpassword",
        )
        while time.time() - start_time < max_timeout:
            try:
                ldap_connection_object.bind()
                break
            except Exception as e:
                if time.time() - start_time >= max_timeout:
                    print(f"Unable to bind to the LDAP server: \n{e}")
                    exit(1)
                else:
                    time.sleep(1)

        ldap_connections["openldap"] = ldap_connection_object

        # Create the users
        for i in range(1, 6):
            user_dn = "cn=test_{},dc=example,dc=org".format(i)
            # XXX ldapPublicKey objectclass can only be created via the config file.
            user_attributes = {
                "objectClass": [
                    "inetOrgPerson",
                    "posixAccount",
                    "organizationalPerson",
                    "person",
                    "top",
                ],
                "uid": f"test_{i}",
                "loginShell": "/bin/bash",
                "sambaAcctFlags": "[U          ]",
                "cn": f"test_{i}",
                "gidNumber": 501,
                "sn": f"test_{i}",
                "mail": f"test_{i}@example.com",
                "displayName": f"test_{i}",
                "givenName": f"test_{i}",
                "gecos": f"test_{i}",
                "userPassword": "password",
            }
            ldap_connection_object.add(user_dn, attributes=user_attributes)

    '''
        # ===
        # Query for the groups
        groups = ["group_1", "group_2", "group_3"]
        for group in groups:
            group_dn = "cn={},dc=example,dc=org".format(group)
            self.ldap_connection_object.search(
                group_dn, "(objectClass=*)", attributes=["member"]
            )

            # Print the members of the group
            for entry in self.ldap_connection_object.entries:
                members = entry.member
                print("\n\n\n\n --------- DEBUG")
                print("Group:", group)
                print("Members:", [str(member) for member in members])
                print("----------------\n\n\n\n")

    def setup_method(self):
        """Ensure the OpenLDAP group {test_group} is completely empty
        before each test.
        """
        self.local_openldap_connection.bind()

    def teardown_method(self):
        """Ensure the OpenLDAP connection is closed after each test."""
        self.openldap_connection.unbind()
    '''

    def test_1(self):
        assert True
