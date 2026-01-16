import json
from pathlib import Path
from typing import Dict

from PIL import Image

from gsuid_core.sv import get_plugin_prefixs

from gsuid_core.help.draw_new_plugin_help import get_new_help
from gsuid_core.help.model import PluginHelp

from ..version import ScoreEchoVersion

ICON = Path(__file__).parent.parent.parent / "ICON.png"
HELP_DATA = Path(__file__).parent / "help.json"
ICON_PATH = Path(__file__).parent / "change_icon_path"
TEXT_PATH = Path(__file__).parent / "texture2d"


def get_footer(color: str = "white") -> Image.Image:
    return Image.open(TEXT_PATH / f"footer_{color}.png")


def get_help_data() -> Dict[str, PluginHelp]:
    if not HELP_DATA.exists():
        return {}
    with open(HELP_DATA, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, dict) else {}


async def get_help(pm: int):
    plugin_help = get_help_data()
    prefixes = get_plugin_prefixs("ScoreEcho")
    plugin_prefix = prefixes[0] if prefixes else ""
    return await get_new_help(
        plugin_name="ScoreEcho",
        plugin_info={f"v{ScoreEchoVersion}": ""},
        plugin_icon=Image.open(ICON),
        plugin_help=plugin_help,
        plugin_prefix=plugin_prefix,
        help_mode="dark",
        banner_bg=Image.open(TEXT_PATH / "banner_bg.jpg"),
        banner_sub_text="分析帮助",
        help_bg=Image.open(TEXT_PATH / "bg.jpg"),
        cag_bg=Image.open(TEXT_PATH / "cag_bg.png"),
        item_bg=Image.open(TEXT_PATH / "item.png"),
        icon_path=ICON_PATH,
        footer=get_footer(),
        enable_cache=False,
        column=4,
        pm=pm,
    )
