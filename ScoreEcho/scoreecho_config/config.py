import os

from gsuid_core.data_store import get_res_path
from gsuid_core.utils.plugins_config.gs_config import StringConfig
from gsuid_core.utils.plugins_config.models import GsStrConfig

CONIFG_DEFAULT = {
    "xwtoken": GsStrConfig("xwtoken", "找小维要", "test"),
    "endpoint": GsStrConfig(
        "endpoint", "xwapi地址", "https://scoreecho.loping151.site/score"
    ),
    "localalias": GsStrConfig(
        "本地别名", "尝试使用本地别名文件", "./XutheringWavesUID/alias/char_alias.json"
    ),
}

CONFIG_PATH = get_res_path() / "ScoreEcho" / "config.json"

os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

seconfig = StringConfig("ScoreEcho", CONFIG_PATH, CONIFG_DEFAULT)
