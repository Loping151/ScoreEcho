from gsuid_core.utils.plugins_config.models import (
    GSC,
    GsStrConfig,
    GsBoolConfig,
    GsListStrConfig,
)

CONIFG_DEFAULT = {
    'xwtoken': GsListStrConfig('xwtoken', '找小维要', ['test']),
    'endpoint': GsListStrConfig('endpoint', 'xwapi地址', ['loping151.site:5678/score'])
}

from gsuid_core.data_store import get_res_path

CONFIG_PATH = get_res_path() / 'ScoreEcho' / 'config.json'

import os

os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

from gsuid_core.utils.plugins_config.gs_config import StringConfig

seconfig = StringConfig('ScoreEcho', CONFIG_PATH, CONIFG_DEFAULT)