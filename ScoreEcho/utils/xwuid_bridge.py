"""xwuid (XutheringWavesUID) 桥接层。

提供:
- ``email_login_entry``：复用 xwuid 的 launcher SDK 登录命令
- ``find_xwuid_net_uid``：在 xwuid 的 ``WavesBind`` 里找该用户绑定的国际服 UID
- ``fetch_baseinfo``：拉 launcher SDK 玩家基础信息(24h 内存缓存)
- ``get_avatar_url``：从 Event 解析头像 URL(QQ 官机 / onebot 通用)

xwuid 不存在时所有方法降级为不可用 / None,不影响 ScoreEcho 主功能。
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event


_NET_UID_THRESHOLD = 200000000
_BASEINFO_TTL = 24 * 3600
_baseinfo_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def is_net_uid(uid: str) -> bool:
    try:
        return int(uid) >= _NET_UID_THRESHOLD
    except (TypeError, ValueError):
        return False


async def email_login_entry(bot: Bot, ev: Event):
    """触发 xwuid 的邮箱登录流程；xwuid 不在时给提示。"""
    try:
        from plugins.XutheringWavesUID.XutheringWavesUID.wutheringwaves_login.email_login import (
            email_login_entry as entry,
        )
    except ImportError:
        at_sender = ev.group_id is not None
        return await bot.send(
            "分析登录依赖 XutheringWavesUID 插件，未检测到该插件。",
            at_sender=at_sender,
        )
    return await entry(bot, ev)


async def find_xwuid_net_uid(user_id: str, bot_id: str) -> Optional[str]:
    """在 xwuid 的 WavesBind 里找该用户绑定的第一个国际服 UID。"""
    try:
        from plugins.XutheringWavesUID.XutheringWavesUID.utils.database.models import (
            WavesBind,
        )
    except ImportError:
        return None
    try:
        uid_list = await WavesBind.get_uid_list_by_game(user_id, bot_id) or []
    except Exception:
        logger.exception("[ScoreEcho] 查询 xwuid WavesBind 失败")
        return None
    for uid in uid_list:
        if is_net_uid(uid):
            return uid
    return None


async def fetch_baseinfo(user_id: str, bot_id: str, uid: str) -> Optional[Dict[str, Any]]:
    """拉取 launcher SDK 玩家基础信息（24h 内存缓存）。

    返回 ``{role_name, union_level, world_level}`` 或 ``None``。
    仅对国际服 UID 生效。
    """
    if not is_net_uid(uid):
        return None
    try:
        from plugins.XutheringWavesUID.XutheringWavesUID.utils.api.launcher_chain import (
            fetch_launcher_panel,
        )
    except ImportError:
        return None

    now = time.time()
    cached = _baseinfo_cache.get(uid)
    if cached and now - cached[0] < _BASEINFO_TTL:
        return cached[1]

    panel = await fetch_launcher_panel(user_id, bot_id, uid)
    if panel is None:
        return None

    base = panel.base
    info: Dict[str, Any] = {
        "role_name": base.name or "",
        "union_level": base.level,
        "world_level": base.worldLevel,
    }
    _baseinfo_cache[uid] = (now, info)
    return info


def get_avatar_url(ev: Event) -> Optional[str]:
    """从 Event 解析头像 URL。

    优先用 ``ev.sender['avatar']``(适配器已经按 onebot / QQ 官机各自填好对应
    的 q.qlogo.cn URL);拿不到再 fallback 到纯数字 user_id 的 QQ 头像 URL;
    都没有返回 None。
    """
    sender = getattr(ev, "sender", None)
    if isinstance(sender, dict):
        avatar = sender.get("avatar")
        if isinstance(avatar, str) and avatar:
            return avatar

    user_id = getattr(ev, "user_id", "") or ""
    if user_id.isdigit():
        return f"https://q.qlogo.cn/headimg_dl?dst_uin={user_id}&spec=640"
    return None
