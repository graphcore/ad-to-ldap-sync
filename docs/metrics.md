# Metrics

## Cyclomatic Complexity and Maintainability Index

<!--lint disable-->

| Filename | Name | Type | Start:End Line | Complexity | Clasification |
| -------- | ---- | ---- | -------------- | ---------- | ------------- |
| src/entrypoint.py | entrypoint | F | 11:35 | 3 | A |
| src/utils/utilities.py | user_exception_lookup | F | 65:88 | 9 | B |
| src/utils/utilities.py | get_next_gid_uid_number | F | 91:136 | 3 | A |
| src/utils/utilities.py | write_monitoring_log | F | 9:37 | 2 | A |
| src/utils/utilities.py | fill_array_gaps | F | 40:62 | 2 | A |
| src/utils/ldap_wrapper.py | LdapInterface | C | 11:147 | 2 | A |
| src/utils/ldap_wrapper.py | LdapInterface.write_manifest | M | 136:147 | 2 | A |
| src/utils/ldap_wrapper.py | LdapWrapper | C | 150:222 | 2 | A |
| src/utils/ldap_wrapper.py | NoOp | C | 227:312 | 2 | A |
| src/utils/ldap_wrapper.py | LdapInterface.\_\_init\_\_ | M | 17:24 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.response | M | 28:30 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.result | M | 33:35 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.unbind | M | 37:41 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.add | M | 43:57 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.delete | M | 59:63 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.modify | M | 65:69 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.modify_dn | M | 71:82 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.search | M | 84:105 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.compare | M | 107:113 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.abandon | M | 115:122 | 1 | A |
| src/utils/ldap_wrapper.py | LdapInterface.extended | M | 124:134 | 1 | A |
| src/utils/ldap_wrapper.py | LdapWrapper.unbind | M | 153:159 | 1 | A |
| src/utils/ldap_wrapper.py | LdapWrapper.search | M | 161:184 | 1 | A |
| src/utils/ldap_wrapper.py | LdapWrapper.add | M | 186:207 | 1 | A |
| src/utils/ldap_wrapper.py | LdapWrapper.modify | M | 211:222 | 1 | A |
| src/utils/ldap_wrapper.py | NoOp.\_\_init\_\_ | M | 230:238 | 1 | A |
| src/utils/ldap_wrapper.py | NoOp.response | M | 241:243 | 1 | A |
| src/utils/ldap_wrapper.py | NoOp.result | M | 246:248 | 1 | A |
| src/utils/ldap_wrapper.py | NoOp.add | M | 250:271 | 1 | A |
| src/utils/ldap_wrapper.py | NoOp.search | M | 274:299 | 1 | A |
| src/utils/ldap_wrapper.py | NoOp.modify | M | 301:312 | 1 | A |
| src/utils/ldap_connections.py | LdapConnections | C | 13:214 | 3 | A |
| src/utils/ldap_connections.py | LdapConnections._create_tls_object | M | 17:57 | 2 | A |
| src/utils/ldap_connections.py | LdapConnections._create_ldap_server_object | M | 59:104 | 2 | A |
| src/utils/ldap_connections.py | LdapConnections._create_ldap_connection_object | M | 106:149 | 2 | A |
| src/utils/ldap_connections.py | LdapConnections._bind_to_ldap | M | 151:195 | 2 | A |
| src/utils/ldap_connections.py | LdapConnections.setup_ldap_connections | M | 197:214 | 2 | A |
| src/utils/manage_argument_parser.py | ManageParser | C | 21:147 | 2 | A |
| src/utils/manage_argument_parser.py | ManageArguments | C | 8:18 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._add_environment | M | 27:36 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._add_config_file | M | 41:47 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._add_group_override | M | 51:57 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._add_universal_override | M | 61:68 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._add_console_log_level | M | 75:82 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._build_parser | M | 85:113 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser.parse_cli_args | M | 115:122 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._parse_args | M | 124:131 | 1 | A |
| src/utils/manage_argument_parser.py | ManageParser._build_args | M | 134:147 | 1 | A |
| src/utils/basic_config.py | BasicConfig | C | 10:83 | 2 | A |
| src/utils/basic_config.py | BasicConfig._load_yaml_file | M | 19:38 | 2 | A |
| src/utils/basic_config.py | BasicConfig._load_config_file | M | 49:61 | 2 | A |
| src/utils/basic_config.py | BasicConfig.\_\_init\_\_ | M | 15:17 | 1 | A |
| src/utils/basic_config.py | BasicConfig._load_exception_file | M | 40:47 | 1 | A |
| src/utils/basic_config.py | BasicConfig._load_country_control_file | M | 63:70 | 1 | A |
| src/utils/basic_config.py | BasicConfig.create_basic_config | M | 72:83 | 1 | A |
| src/runners/group_sync.py | AdLdapGroupSync._lookup_ad_user | M | 1075:1155 | 8 | B |
| src/runners/group_sync.py | AdLdapGroupSync._generate_additions | M | 710:771 | 6 | B |
| src/runners/group_sync.py | AdLdapGroupSync._check_override_required | M | 968:1073 | 6 | B |
| src/runners/group_sync.py | AdLdapGroupSync._check_process_changes | M | 1262:1338 | 6 | B |
| src/runners/group_sync.py | AdLdapGroupSync._flatten_nested_group | M | 460:515 | 5 | A |
| src/runners/group_sync.py | AdLdapGroupSync._check_country_control | M | 615:658 | 5 | A |
| src/runners/group_sync.py | AdLdapGroupSync._new_ldap_group | M | 1340:1449 | 5 | A |
| src/runners/group_sync.py | AdLdapGroupSync | C | 17:1545 | 4 | A |
| src/runners/group_sync.py | AdLdapGroupSync._build_sync_group_list | M | 560:613 | 4 | A |
| src/runners/group_sync.py | AdLdapGroupSync._find_user_in_source_dict | M | 660:708 | 4 | A |
| src/runners/group_sync.py | AdLdapGroupSync._get_account_data | M | 1158:1200 | 4 | A |
| src/runners/group_sync.py | AdLdapGroupSync._process_operations | M | 1202:1259 | 4 | A |
| src/runners/group_sync.py | AdLdapGroupSync._modify_group | M | 198:249 | 3 | A |
| src/runners/group_sync.py | AdLdapGroupSync._create_group_dictionary | M | 358:458 | 3 | A |
| src/runners/group_sync.py | AdLdapGroupSync._check_ad_object_type | M | 517:557 | 3 | A |
| src/runners/group_sync.py | AdLdapGroupSync._generate_deletions | M | 773:830 | 3 | A |
| src/runners/group_sync.py | AdLdapGroupSync._add_missing_openldap_groups | M | 1452:1500 | 3 | A |
| src/runners/group_sync.py | AdLdapGroupSync._group_search | M | 51:113 | 2 | A |
| src/runners/group_sync.py | AdLdapGroupSync._determine_user_base | M | 116:147 | 2 | A |
| src/runners/group_sync.py | AdLdapGroupSync._determine_group_name | M | 252:273 | 2 | A |
| src/runners/group_sync.py | AdLdapGroupSync._determine_group_id | M | 275:315 | 2 | A |
| src/runners/group_sync.py | AdLdapGroupSync._determine_group_members | M | 317:356 | 2 | A |
| src/runners/group_sync.py | AdLdapGroupSync._generate_group_operations | M | 832:904 | 2 | A |
| src/runners/group_sync.py | AdLdapGroupSync.\_\_init\_\_ | M | 43:49 | 1 | A |
| src/runners/group_sync.py | AdLdapGroupSync._user_search | M | 149:196 | 1 | A |
| src/runners/group_sync.py | AdLdapGroupSync._determine_change_percent | M | 907:966 | 1 | A |
| src/runners/group_sync.py | AdLdapGroupSync._main | M | 1503:1545 | 1 | A |
| src/runners/user_sync.py | AdLdapUserSync._generate_password | M | 217:250 | 13 | C |
| src/runners/user_sync.py | AdLdapUserSync._check_user_enable_disable | M | 509:555 | 12 | C |
| src/runners/user_sync.py | AdLdapUserSync._build_attr_changes | M | 611:700 | 11 | C |
| src/runners/user_sync.py | AdLdapUserSync._convert_lists_to_strings | M | 558:609 | 9 | B |
| src/runners/user_sync.py | AdLdapUserSync._get_all_users | M | 109:176 | 7 | B |
| src/runners/user_sync.py | AdLdapUserSync | C | 21:803 | 6 | B |
| src/runners/user_sync.py | AdLdapUserSync._update_ldap_account | M | 305:342 | 6 | B |
| src/runners/user_sync.py | AdLdapUserSync._attr_ascii_compare | M | 702:767 | 6 | B |
| src/runners/user_sync.py | AdLdapUserSync._get_user_attributes | M | 55:107 | 4 | A |
| src/runners/user_sync.py | AdLdapUserSync._set_random_ldap_password | M | 252:303 | 4 | A |
| src/runners/user_sync.py | AdLdapUserSync._check_change | M | 462:506 | 4 | A |
| src/runners/user_sync.py | AdLdapUserSync._get_next_sambasid | M | 178:215 | 3 | A |
| src/runners/user_sync.py | AdLdapUserSync._add_class_to_ldap_account | M | 344:406 | 3 | A |
| src/runners/user_sync.py | AdLdapUserSync._new_ldap_account | M | 408:460 | 2 | A |
| src/runners/user_sync.py | AdLdapUserSync._main | M | 769:803 | 2 | A |
| src/runners/user_sync.py | AdLdapUserSync.\_\_init\_\_ | M | 47:53 | 1 | A |

<!--lint enable-->

## Raw Metrics

```bash
** Total **
    LOC: 3279
    LLOC: 1024
    SLOC: 1676
    Comments: 25
    Single comments: 45
    Multi: 1270
    Blank: 288
    - Comment Stats
        (C % L): 1%
        (C % S): 1%
        (C + M % L): 39%
```
