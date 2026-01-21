from pathlib import Path

from gsuid_core.data_store import get_res_path

MAIN_PATH = get_res_path() / "ScoreEcho"
USER_PATH = MAIN_PATH / "user"

# 本插件的别名资源路径
ALIAS_PATH = MAIN_PATH / "resource" / "map" / "alias"
CHAR_ALIAS_PATH = ALIAS_PATH / "char_alias.json"

# 兼容旧版本：如果本插件没有别名资源，尝试从 XWUID 获取
XW_MAIN_PATH = get_res_path() / "XutheringWavesUID"
XW_ALIAS_PATH = XW_MAIN_PATH / "resource" / "map" / "alias"
XW_CHAR_ALIAS_PATH = XW_ALIAS_PATH / "char_alias.json"


def init_dir() -> None:
    USER_PATH.mkdir(parents=True, exist_ok=True)
    ALIAS_PATH.mkdir(parents=True, exist_ok=True)


def get_user_dir(user_id: str, uid: str) -> Path:
    return USER_PATH / str(user_id) / str(uid)


init_dir()
