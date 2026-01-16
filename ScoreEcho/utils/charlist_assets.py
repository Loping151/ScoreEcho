import json
import shutil
from pathlib import Path
from typing import Dict, Optional

from gsuid_core.data_store import get_res_path

SCOREECHO_ASSET_ROOT = get_res_path() / "ScoreEcho" / "charlist"
TEXTURE_PATH = SCOREECHO_ASSET_ROOT / "texture2d"
FONT_PATH = SCOREECHO_ASSET_ROOT / "fonts"
AVATAR_PATH = SCOREECHO_ASSET_ROOT / "avatar"
MAP_PATH = SCOREECHO_ASSET_ROOT / "map"


def _get_xwuid_plugin_root() -> Path:
    return Path(__file__).resolve().parents[4] / "XutheringWavesUID" / "XutheringWavesUID"


def _get_xwuid_texture_path() -> Path:
    return _get_xwuid_plugin_root() / "wutheringwaves_charlist" / "texture2d"


def _get_xwuid_fonts_path() -> Path:
    return _get_xwuid_plugin_root() / "utils" / "fonts"


XW_FONT_PATH = _get_xwuid_fonts_path()


def _get_xwuid_resource_path() -> Path:
    return get_res_path() / "XutheringWavesUID" / "resource"


def _copy_tree_once(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def _copy_file_once(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def ensure_assets() -> None:
    _copy_tree_once(_get_xwuid_texture_path(), TEXTURE_PATH)
    map_src = _get_xwuid_resource_path() / "map" / "id2name.json"
    _copy_file_once(map_src, MAP_PATH / "id2name.json")
    AVATAR_PATH.mkdir(parents=True, exist_ok=True)


def load_name_id_map() -> Dict[str, str]:
    ensure_assets()
    id2name_path = MAP_PATH / "id2name.json"
    if not id2name_path.exists():
        return {}
    with open(id2name_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return {name: str(role_id) for role_id, name in data.items()}


def ensure_avatar(role_id: str) -> Optional[Path]:
    ensure_assets()
    if not role_id:
        return None
    filename = f"role_head_{role_id}.png"
    dst = AVATAR_PATH / filename
    if dst.exists():
        return dst
    src = _get_xwuid_resource_path() / "waves_avatar" / filename
    if not src.exists():
        return None
    shutil.copy2(src, dst)
    return dst


def get_score_icon_path(score_level: str) -> Path:
    return TEXTURE_PATH / f"score_{score_level.lower()}.png"
