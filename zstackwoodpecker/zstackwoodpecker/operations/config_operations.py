'''

All zstack config operations

@author: Youyk
'''
import os

import apibinding.api_actions as api_actions
import apibinding.inventory as inventory
import account_operations
import zstackwoodpecker.test_util as test_util

def get_global_config_value(category, name, session_uuid = None, \
        default_value = None):
    value = None
    action = api_actions.GetGlobalConfigAction()
    action.category = category
    action.name = name
    test_util.action_logger('Get global config category: %s, name: %s' \
            % (category, name))
    result = account_operations.execute_action_with_session(action, \
            session_uuid)

    if result:
        return result.inventory.value

def get_global_config_default_value(category, name, session_uuid = None):
    value = None
    return get_global_config_value(category, name, session_uuid, True)

def change_global_config(category, name, value, session_uuid = None):
    default_value = get_global_config_default_value(category, name, session_uuid)
    pre_value = get_global_config_value(category, name, session_uuid)
    action = api_actions.UpdateGlobalConfigAction()
    action.category = category
    action.name = name
    action.defaultValue = str(default_value)
    if value:
        action.value = str(value)
    test_util.action_logger('change global config category: %s, name: %s, to %s' % (category, name, value))
    account_operations.execute_action_with_session(action, session_uuid)

    return pre_value

