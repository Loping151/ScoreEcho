"""init"""

from gsuid_core.sv import Plugins
from pathlib import Path
import os, json

Plugins(name="ScoreEcho", force_prefix=["ww"], allow_empty_prefix=False, priority=3)

from gsuid_core.data_store import get_res_path
DATA_PATH = get_res_path()

change_made = False
if os.path.exists(
    DATA_PATH / 'ScoreEcho' / 'config.json'
):
    with open(
        DATA_PATH/ 'ScoreEcho' / 'config.json', 'r', encoding='utf-8'
    ) as f:
        se_config_data = json.load(f)
        if type(se_config_data.get('xwtoken', {}).get("data")) is list:
            se_config_data['xwtoken']['data'] = se_config_data['xwtoken']['data'][0]
            se_config_data['xwtoken']['type'] = "GsStrConfig"
            change_made = True
        if type(se_config_data.get('endpoint', {}).get("data")) is list:
            se_config_data['endpoint']['data'] = ":".join(se_config_data['endpoint']['data'])
            se_config_data['endpoint']['type'] = "GsStrConfig"
            change_made = True
        if type(se_config_data.get('localalias', {}).get("data")) is list:
            se_config_data['localalias']['data'] = se_config_data['localalias']['data'][0]
            se_config_data['localalias']['type'] = "GsStrConfig"
            change_made = True
if change_made:
    with open(
        Path(DATA_PATH) / 'ScoreEcho' / 'config.json', 'w', encoding='utf-8'
    ) as f:
        json.dump(se_config_data, f, ensure_ascii=False, indent=4)

# noqa: F401 - Imported to initialize SV objects
from . import scoreecho_config, scoreecho_help, scoreecho_score, scoreecho_user