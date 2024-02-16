# Configuration details

This document describes all the entries for the main configuration file.

See [template](../config/config-template.yaml) for sample values.

## Settings

<!--lint disable-->
| Entry | Type | Description |
| ----- | ---- | ----------- |
|`small_group_blind_update`|int|Groups below this size will automatically update regardless of how many changes there are.|
|`total_change_threshold`|int|Threshold at which point override is required for the total number of changes.|
|`deletions_change_threshold`|int|Threshold at which point override is required for the number of deletions.|
|`additions_change_threshold`|int|Threshold at which point override is required for the number of additions.|
|`exception_file`|str|Location of the exception file.|
|`country_control_file`|str|Location of the country control file.|
|`monitoring_log_file`|str|Location of the monitoring log file.|
|`manifest_path`|str|Location of the manifest log file.|
|`log_file`|str|Log file name.|
|`log_file_level`|str|Log level. See [Loguru levels](https://loguru.readthedocs.io/en/stable/api/logger.html#levels) for details.|
|`log_file_retention`|int|How many log files to retain. See [Loguru documentation](https://loguru.readthedocs.io/en/stable/api/logger.html)|
|`log_file_rotation`|str|How often to rotate. See [Loguru documentation](https://loguru.readthedocs.io/en/stable/api/logger.html)|
|`special_password_characters`|str|List of special characters allowed in passwords.|
|`banned_password_chars`|str|List of characters denied in passwords.|
|`password_length`|str|Lenght of the password.|
|`ms_ad_active_account_ids`|list[int]|See [MS user account control](https://jackstromberg.com/2013/01/useraccountcontrol-attributeflag-values/)|

<!--lint enable-->

## LDAP

<!--lint disable-->
| Entry &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; | Type | Description |
| ----- | ---- | ----------- |
|`server`|str|The FQDN of the LDAP server.|
|`port`|int|The port to connect on.|
|`get_info`|str|Control schema behavior. See Python [LDAP3](https://ldap3.readthedocs.io/en/latest/schema.html?highlight=get_info#schema) documentation.|
|`ciphers`|str|Which ciphers to allow. See Python [LDAP3](https://ldap3.readthedocs.io/en/latest/ssltls.html?highlight=ciphers#the-tls-object) documentation.|
|`ssl`|dict[str]|SSL configuration options. See Python [LDAP3](https://ldap3.readthedocs.io/en/latest/ssltls.html) documentation.|
|`-->` `enabled`|bool|Enable or disable SSL|
|`-->` `validate`|str|What type of validation to perform. See above documentation.|
|`-->` `version`|str|Specific version of TLS to use. See above documentation.|
|`-->` `ca_certs_file`|str|Path of the certificate.|
|`bind_user`|str|User to use.
|`bind_pass`|str|Password to use.
|`schema`| |Information about the specific directory and it's relevant data structures.|
|`-->` `sid_prefix`|str|The Windows security identifier (SID) prefix.|
|`-->` `base`|str|The base string to use when building up the distinguished name.|
|`-->` `users`|str|The lowest common path in the tree where to expect users. In OpenLDAP specifically, where users are created. Further used in schema base to generate the full path.|
|`-->` `groups`|str|The OU where we expect the group for synchronisation to exists.|
|`-->` `user_sync_ous`|list[str]|The OU(s) where we expect the users for synchronisation to exists.|
|`-->` `remote_synced_attrs`|dict[str]|Which local directory attributes to synchronisation to the corresponding remote directory attributes.|
|`-->` `not_synced_attrs`|list[str]|The list of attributes we do not synchronise. These attributes are required for other actions.|
|`-->` `local_copy_attrs`||Which local directory attributes to synchronisation to the corresponding local directory attributes. Example: `displayname` to `gecos`.|
|`-->` `disable_user_mask`|list[str]|The default set of attributes assigned to a disabled users. No entries should match what is in `enable_user_maks`.|
|`-->` `enable_user_mask`|list[str]|The default set of attributes assigned to an enabled user. No entries should match what is in `disable_user_maks`.|
|`-->` `new_group`||Information about creating new groups.|
|`---->` `min_member_number`|int|When selecting a new UID, it will be no lower than this number.|
|`---->` `mask`||Default values for a new group.|
|`------>` `objectClass`|list[str]|The list of object classes for a new group.|
|`------>` `attributes`|dict[str]|The dictionary of attributes for a new group.|
|`-->` `new_user`||Information about creating a new user.|
|`---->` `min_member_number`|int|Minimum UID to start searching for the next available UID.|
|`---->` `mask`||Default values for a new user.|
|`------>` `objectClass`|list[str]|The list of object classes for a new user.|
|`------>` `attributes`|dict[str]|The dictionary of attributes for a new user.|
|`-->` `objects`||The mapping for specific values in different LDAP implementations.|
|`---->` `user`||Specific mappings for the user object class.|
|`------>` `name`|str|Value name used for the objects identifier.|
|`------>` `obj_class`|str|What object class is assigned to users in the LDAP implementation.|
|`------>` `sid`|str|Value name used for the objects SID.|
|`------>` `uid_number`|str|Value name used for the objects UNIX UID.|
|`---->` `group`||Specific mappings for the group object class.|
|`------>` `name`|str|Value name used for the objects identifier.|
|`------>` `obj_class`|str|What object class is assigned to groups in the LDAP implementation.|
|`------>` `gid_number`|str|Value name used for the objects UNIX GID.|
|`------>` `members`|str|Value name used for the member list of this group.|

<!--lint enable-->
