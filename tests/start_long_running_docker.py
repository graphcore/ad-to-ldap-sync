#!/usr/bin/env python
"""Try to start a Docker container for integration tests.

If your application don't need such a container,
simply sys.exit(0) without any output.
"""

import docker  # type: ignore
import time
import os
from ldap3 import Server, Connection


client = docker.from_env()
ldif_files = f"{os.getcwd()}/tests/data/ldif"
try:
    container = client.containers.run(
        "bitnami/openldap:latest",
        name="OpenLDAP-int-test",
        detach=True,
        ports={"1389/tcp": "1389/tcp"},
        environment={
            "LDAP_ROOT": "dc=example,dc=org",
            "LDAP_ADMIN_USERNAME": "admin",
            "LDAP_ADMIN_PASSWORD": "adminpassword",
            "LDAP_LOGLEVEL": 64,
            "LDAP_EXTRA_SCHEMAS": "cosine,nis,inetorgperson,samba,openssh-lpk,autofs",
        },
        volumes={ldif_files: {"bind": "/schemas", "mode": "ro"}},
    )
    network = client.networks.get("python-testing")
    network.connect("OpenLDAP-int-test")
except Exception as e:
    print(f"Unable to start Docker container: \n{e}")
    exit(1)

ldap_server_object = Server("localhost", port=1389, get_info="ALL")
ldap_connection_object = Connection(
    ldap_server_object, user="cn=admin,dc=example,dc=org", password="adminpassword"
)

max_timeout = 10
start_time = time.time()
while time.time() - start_time < max_timeout:
    try:
        ldap_connection_object.bind()
        # Ensure we only return the first 13 characters of the Docker ID.
        # This is used in the Makefile, so if you modify it make sure to
        # check what is going on in the Makefile.
        print(client.api.inspect_container(container.id)["Id"][0:12])
        ldap_connection_object.unbind()
        break
    except Exception as e:
        if time.time() - start_time >= max_timeout:
            print(f"Unable to bind to the LDAP server: \n{e}")
            exit(1)
        else:
            time.sleep(1)
