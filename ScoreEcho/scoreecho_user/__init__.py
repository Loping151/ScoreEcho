import json
import re
from pathlib import Path
from typing import Dict, Optional

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV, get_plugin_prefixs

from ..utils.database.models import ScoreUser
from ..utils.resource import XW_CHAR_ALIAS_PATH, get_user_dir

try:
    from ....XutheringWavesUID.XutheringWavesUID.utils.char_info_utils import PATTERN
    from ....XutheringWavesUID.XutheringWavesUID.utils.name_convert import (
        alias_to_char_name_optional,
    )
except Exception:  # pragma: no cover - fallback if dependency missing
    PATTERN = r"[\u4e00-\u9fa5a-zA-Z0-9]{1,15}"
    alias_to_char_name_optional = None

PREFIXES = get_plugin_prefixs("ScoreEcho")
sv_score_user = SV("ScoreEcho用户绑定", priority=9)
sv_score_setting = SV("ScoreEcho设置", priority=3)


def _get_char_info_path(user_id: str, uid: str) -> Path:
    return get_user_dir(user_id, uid) / "char_info.json"


def _load_char_info(path: Path) -> Dict[str, str]:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    if "用户名" not in data:
        data["用户名"] = ""
    return data


def _save_char_info(path: Path, data: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def _get_bound_uid(ev: Event) -> Optional[str]:
    return await ScoreUser.get_uid_by_game(ev.user_id, ev.bot_id)


def _check_alias_path() -> Optional[str]:
    if not XW_CHAR_ALIAS_PATH.exists():
        return f"别名文件不存在：{XW_CHAR_ALIAS_PATH}"
    return None


def _resolve_char_name(raw_name: str) -> Optional[str]:
    if alias_to_char_name_optional is None:
        return None
    return alias_to_char_name_optional(raw_name)


def _format_msg(msg: str, is_group: bool) -> str:
    """根据聊天类型格式化消息"""
    if is_group:
        return " " + msg
    return msg


@sv_score_user.on_command(
    ("分析绑定", "分析切换", "分析查看", "分析删除", "分析删除全部"),
    block=True,
)
async def score_user_bind(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = ''.join(filter(str.isdigit, ev.text.strip()))
    user_id = ev.user_id

    if "分析绑定" in ev.command:
        if not uid:
            return await bot.send(_format_msg(f"请使用【{PREFIXES[0]}分析绑定 UID】进行绑定", is_group), at_sender=is_group)
        code = await ScoreUser.insert_uid(user_id, ev.bot_id, uid, ev.group_id)
        if code in (0, -2):
            await ScoreUser.switch_uid_by_game(user_id, ev.bot_id, uid)
        msg_map = {
            0: f"分析UID[{uid}]绑定成功！",
            -1: f"分析UID[{uid}]位数不正确或为空！",
            -2: f"分析UID[{uid}]已经绑定过了！",
            -3: "你输入了错误的格式！",
        }
        return await bot.send(_format_msg(msg_map.get(code, "绑定失败，请稍后再试"), is_group), at_sender=is_group)

    if "分析切换" in ev.command:
        if not uid:
            return await bot.send(_format_msg(f"请使用【{PREFIXES[0]}分析切换 UID】进行切换", is_group), at_sender=is_group)
        retcode = await ScoreUser.switch_uid_by_game(user_id, ev.bot_id, uid)
        if retcode == 0:
            cur_uid = await ScoreUser.get_uid_by_game(user_id, ev.bot_id)
            return await bot.send(_format_msg(f"已切换当前分析UID为[{cur_uid}]", is_group), at_sender=is_group)
        if retcode == -3:
            return await bot.send(_format_msg("当前仅绑定一个UID，无需切换", is_group), at_sender=is_group)
        return await bot.send(_format_msg("尚未绑定该UID或未绑定任何UID", is_group), at_sender=is_group)

    if "分析查看" in ev.command:
        uid_list = await ScoreUser.get_uid_list_by_game(user_id, ev.bot_id)
        if not uid_list:
            return await bot.send(_format_msg("尚未绑定任何UID", is_group), at_sender=is_group)
        current_uid = uid_list[0]
        uids = "\n".join(uid_list)
        msg = f"当前使用UID：{current_uid}\n已绑定UID列表：\n{uids}"
        return await bot.send(_format_msg(msg, is_group), at_sender=is_group)

    if "分析删除全部" in ev.command:
        retcode = await ScoreUser.update_data(
            user_id=user_id,
            bot_id=ev.bot_id,
            **{ScoreUser.get_gameid_name(None): None},
        )
        if retcode == 0:
            return await bot.send(_format_msg("已删除全部绑定UID", is_group), at_sender=is_group)
        return await bot.send(_format_msg("尚未绑定任何UID", is_group), at_sender=is_group)

    if not uid:
        return await bot.send(_format_msg(f"请使用【{PREFIXES[0]}分析删除 UID】删除", is_group), at_sender=is_group)
    data = await ScoreUser.delete_uid(user_id, ev.bot_id, uid)
    msg_map = {0: f"已删除UID[{uid}]", -1: f"UID[{uid}]不在绑定列表中"}
    return await bot.send(_format_msg(msg_map.get(data, "删除失败，请稍后再试"), is_group), at_sender=is_group)


@sv_score_setting.on_regex(r"^分析设置\s*用户名\s*(?P<name>.+)$", block=True)
async def score_set_username(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send(_format_msg("请先绑定UID后再设置用户名", is_group), at_sender=is_group)
    user_name = ev.regex_dict.get("name") if isinstance(ev.regex_dict, dict) else None
    if not user_name:
        return await bot.send(_format_msg("请提供用户名内容", is_group), at_sender=is_group)
    char_info_path = _get_char_info_path(ev.user_id, uid)
    data = _load_char_info(char_info_path)
    data["用户名"] = user_name.strip()
    _save_char_info(char_info_path, data)
    return await bot.send(_format_msg("已设置用户名", is_group), at_sender=is_group)


@sv_score_setting.on_regex(rf"^分析设置\s*(?P<role>{PATTERN})\s*信息\s*(?P<info>.+)$", block=True)
async def score_set_role_info(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send(_format_msg("请先绑定UID后再设置角色信息", is_group), at_sender=is_group)
    alias_error = _check_alias_path()
    if alias_error:
        return await bot.send(_format_msg(alias_error, is_group), at_sender=is_group)
    raw_name = ev.regex_dict.get("role") if isinstance(ev.regex_dict, dict) else None
    raw_info = ev.regex_dict.get("info") if isinstance(ev.regex_dict, dict) else None
    if not raw_name or not raw_info:
        return await bot.send(_format_msg("请提供角色名", is_group), at_sender=is_group)
    resolved = _resolve_char_name(raw_name.strip())
    if not resolved:
        return await bot.send(_format_msg("未找到对应的角色别名，请检查输入", is_group), at_sender=is_group)
    info = raw_info.strip()
    replacements = {
        "技能等级": "技能",
        "角色": "换角色",
        "人物": "换角色",
        "面板": "换角色",
        "信息": "换角色",
        "个人信息": "换角色",
        "武器": "换武器",
        "装备": "换武器",
        "合鸣": "换合鸣",
        "套装": "换合鸣",
        "声骸": "换声骸",
        "圣遗物": "换声骸",
        "敌人": "换敌人",
        "环境": "换敌人",
        "怪": "换敌人",
        "怪物": "换敌人",
        "敌人信息": "换敌人",
        "怪物信息": "换敌人",
    }
    for key, value in replacements.items():
        info = re.sub(rf"(?<!换){key}", value, info)
    char_info_path = _get_char_info_path(ev.user_id, uid)
    data = _load_char_info(char_info_path)
    data[resolved] = info
    _save_char_info(char_info_path, data)
    return await bot.send(_format_msg(f"已设置{resolved}信息", is_group), at_sender=is_group)


@sv_score_setting.on_regex(rf"^分析查看\s*(?P<role>{PATTERN})\s*信息$", block=True)
async def score_view_role_info(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send(_format_msg("请先绑定UID后再查看角色信息", is_group), at_sender=is_group)
    alias_error = _check_alias_path()
    if alias_error:
        return await bot.send(_format_msg(alias_error, is_group), at_sender=is_group)
    raw_name = ev.regex_dict.get("role") if isinstance(ev.regex_dict, dict) else None
    if not raw_name:
        return await bot.send(_format_msg("请提供角色名", is_group), at_sender=is_group)
    resolved = _resolve_char_name(raw_name.strip())
    if not resolved:
        return await bot.send(_format_msg("未找到对应的角色别名，请检查输入", is_group), at_sender=is_group)
    char_info_path = _get_char_info_path(ev.user_id, uid)
    data = _load_char_info(char_info_path)
    info = data.get(resolved)
    if not info:
        return await bot.send(_format_msg(f"尚未设置{resolved}信息", is_group), at_sender=is_group)
    return await bot.send(_format_msg(f"{resolved}信息：{info}", is_group), at_sender=is_group)
