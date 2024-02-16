"""This is the main entrypoint for the application."""
import sys
from loguru import logger
from utils.manage_argument_parser import ManageParser
from runners.user_sync import AdLdapUserSync
from runners.group_sync import AdLdapGroupSync
from utils.basic_config import BasicConfig
from utils.ldap_connections import LdapConnections


def entrypoint() -> None:
    """Simple entrypoint method."""
    args = ManageParser().parse_cli_args()

    basic_config = BasicConfig(args).create_basic_config()
    logger.remove(0)  # Remove the default logger
    logger.add(
        sys.stdout,
        format=f"{{time}} {args.environment} {{module}} {{level}} {{message}}",
        level=args.console_log_level,
    )
    logger.add(
        f"{args.op_type}_{basic_config['config']['settings']['log_file']}",
        format=f"{{time}} {args.environment} {{module}} {{level}} {{message}}",
        level=basic_config["config"]["settings"]["log_file_level"],
        retention=basic_config["config"]["settings"]["log_file_retention"],
        rotation=basic_config["config"]["settings"]["log_file_rotation"],
    )
    ldap_connections = LdapConnections().setup_ldap_connections(basic_config)
    if basic_config["args"].op_type == "user_sync":
        logger.info("Starting user synchronization ...")
        AdLdapUserSync(basic_config, ldap_connections)
    elif basic_config["args"].op_type == "group_sync":
        logger.info("Starting group synchronization ...")
        AdLdapGroupSync(basic_config, ldap_connections)
