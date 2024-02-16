"""This module is used for ad-hoc utilities."""
import sys
from typing import Any
from pathlib import Path
from ldap3 import Connection
from loguru import logger


def write_monitoring_log(
    basic_config: dict[str, Any], run_status: bool, runner: str
) -> None:
    """Write the monitoring log with the run status.

    Parameters
    ----------
    basic_config :
        The basic configuration as per BasicConfig.
    run_status :
        True if the run was a success, False otherwise.
    runner :
        The runner this was called from. This will write a monitoring log file for
        that runner.

    Raises
    ------
    Exception
        Any error should log to STDOUT and exit with failure.
    """
    config: dict[str, Any] = basic_config["config"]
    try:
        Path(f"{runner}_{config['settings']['monitoring_log_file']}").write_text(
            str(run_status)
        )
    except OSError as exc:
        logger.error("Unable to open file:")
        logger.error(exc)
        sys.exit(1)


def fill_array_gaps(numbers: list[int], offset: int) -> int:
    """Find a gap in an unsorted array of numbers with regards to the offset.

    Given a list of [200, 202, 190, 201, 204] and an offset of 200, return 202.

    If there are no gaps, the highest value + 1 will be returned so long as
    said value is greater than the offset.

    Parameters
    ----------
    numbers :
        A list of integers.
    offset :
        An integer.

    Returns
    -------
    An integer.
    """
    numbers.sort()
    while offset in numbers:
        offset += 1
    return offset


def user_exception_lookup(
    basic_config: dict[str, Any], all_users: dict[str, Any]
) -> None:
    """Lookup users in the exception table.

    Parameters
    ----------
    basic_config :
        The basic configuration as per BasicConfig.
    all_users :
        A dictionary containing all the users and acting as a cache.
    """
    ad_primary_key = basic_config["config"]["ad"]["schema"]["objects"]["user"]["name"]
    for user in all_users.copy():
        if all_users[user].get("ad"):
            if all_users[user]["ad"][ad_primary_key] in basic_config["exceptions"]:
                exception = basic_config["exceptions"].get(user)
                if exception and exception != "NONE":
                    if not all_users.get(exception):
                        all_users[exception] = {}
                    all_users[exception]["ad"] = all_users[user]["ad"]
                    all_users.pop(user)
                elif exception and exception == "NONE":
                    all_users[user]["ad"]["uid"] = "NONE"


def get_next_gid_uid_number(
    basic_config: dict[str, Any],
    ldap_connections: dict[str, Connection],
    server_type: str,
    member: str,
) -> int:
    """Find the next available LDAP gid or uid number.

    Parameters
    ----------
    basic_config :
        The basic configuration as per BasicConfig.
    ldap_connections :
        Dictionary containing both the MS AD and OpenLDAP connections.
    server_type :
        Either "ad" for MS AD or "openldap" for OpenLDAP.
        This maps to the config section of the required server.
    member :
        Either "group" or "user".

    Returns
    -------
    An integer.
    """
    openldap = ldap_connections["openldap"]
    member_lookup = {"user": "uid_number", "group": "gid_number"}
    member_number = basic_config["config"]["openldap"]["schema"]["objects"][member][
        member_lookup[member]
    ]
    min_member_number = basic_config["config"]["openldap"]["schema"][f"new_{member}"][
        "min_member_number"
    ]
    base_string = f"{basic_config['config']['openldap']['schema']['base']}"
    filter_string = f"({member_number}=*)"
    gid_number_list = [0]
    openldap.search(
        base_string,
        filter_string,
        attributes=member_number,
    )
    for entry in openldap.response:
        if isinstance(entry["attributes"][member_number], int):
            gid_number_list.append(entry["attributes"][member_number])
        else:
            logger.warning(f"Found an unexpected {member_number}: {entry}")
    return fill_array_gaps(gid_number_list, min_member_number)
