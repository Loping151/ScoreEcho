import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

import httpx
from PIL import Image
from gsuid_core.bot import Bot
from gsuid_core.data_store import get_res_path
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV, get_plugin_prefixs

from ..scoreecho_config.config import seconfig
from ..utils.database.models import ScoreUser
from ..utils.resource import CHAR_ALIAS_PATH, XW_CHAR_ALIAS_PATH, get_user_dir
from ..utils.charlist_draw import draw_charlist_image
from ..utils.char_utils import PATTERN, alias_to_char_name_optional


sv_phantom_panel = SV("鸣潮声骸角色面板", priority=3)
sv_phantom_score = SV("鸣潮声骸评分", priority=10)
sv_phantom_analysis = SV("鸣潮声骸分析", priority=10)
sv_phantom_rank = SV("鸣潮声骸练度", priority=3)
PREFIXES = get_plugin_prefixs("ScoreEcho")


async def get_image(ev: Event):
    res = []
    for content in ev.content:
        if (
            content.type == "img"
            and content.data
            and isinstance(content.data, str)
            and content.data.startswith("http")
        ):
            res.append(content.data)
        elif (
            content.type == "image"
            and content.data
            and isinstance(content.data, str)
            and content.data.startswith("http")
        ):
            res.append(content.data)

    if not res and ev.image:
        res.append(ev.image)

    return res


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


def _load_result_data(path: Path) -> Dict[str, object]:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    return data if isinstance(data, dict) else {}


def _save_result_data(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_local_alias_path() -> Optional[Path]:
    local_alias_path = seconfig.get_config("localalias").data
    if not local_alias_path:
        return XW_CHAR_ALIAS_PATH if XW_CHAR_ALIAS_PATH.exists() else None
    if local_alias_path.startswith("."):
        candidate = get_res_path() / local_alias_path[2:]
    else:
        candidate = Path(local_alias_path)
    if candidate.exists():
        return candidate
    return XW_CHAR_ALIAS_PATH if XW_CHAR_ALIAS_PATH.exists() else candidate


def _check_alias_path() -> Optional[str]:
    """检查别名文件路径是否存在"""
    alias_path = _get_alias_path()
    if not alias_path or not alias_path.exists():
        return f"别名文件不存在：{alias_path}"
    return None


def _get_alias_path() -> Path:
    """获取别名文件路径，优先使用本地路径"""
    local_path = _get_local_alias_path()
    if local_path and local_path.exists():
        return local_path
    # 兼容：如果本地不存在，尝试使用本插件的别名资源
    if CHAR_ALIAS_PATH.exists():
        return CHAR_ALIAS_PATH
    # 最后尝试 XWUID 的别名资源
    if XW_CHAR_ALIAS_PATH.exists():
        return XW_CHAR_ALIAS_PATH
    return CHAR_ALIAS_PATH  # 返回默认路径（即使不存在）


def _replace_alias(command_str: str, alias_path: Path) -> str:
    matched_name = None
    try:
        with open(alias_path, "r", encoding="utf-8") as f:
            alias_data = json.load(f)
        for char_name, alias_list in alias_data.items():
            for alias in sorted(alias_list, key=len, reverse=True):
                if alias in command_str:
                    command_str = command_str.replace(alias, char_name)
                    logger.info(f"替换别名: {alias} -> {char_name}")
                    matched_name = char_name
                    break
    except Exception as e:
        logger.error(f"加载本地别名文件失败: {e}")
    return command_str, matched_name


def _build_command_str(raw_text: str) -> str:
    for prefix in PREFIXES:
        raw_text = (
            raw_text.replace(prefix, "")
            .replace("C", "")
            .replace("c", "")
            .replace("ost", "")
            .replace("OST", "")
            .replace("|", " ")
            .strip()
        )
    return raw_text


def _extract_role_from_command(command_str: str) -> str:
    parts = command_str.split("换")[0].replace("分析", "").strip().split()
    return parts[0] if parts else ""


async def _encode_images(upload_images):
    images_b64 = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for image_url in upload_images:
            resp = await client.get(image_url)
            resp.raise_for_status()
            image_bytes = resp.content

            max_size_bytes = 2 * 1024 * 1024

            with Image.open(BytesIO(image_bytes)) as img:
                if img.mode not in ("RGB",):
                    img = img.convert("RGB")

                output_buffer = BytesIO()
                quality = 100

                while quality > 10:
                    output_buffer.seek(0)
                    output_buffer.truncate()
                    img.save(output_buffer, format="WEBP", quality=quality)
                    if output_buffer.tell() < max_size_bytes:
                        break
                    quality -= 5

                compressed_image_bytes = output_buffer.getvalue()

            images_b64.append(base64.b64encode(compressed_image_bytes).decode("utf-8"))
    return images_b64


async def _get_bound_uid(ev: Event) -> Optional[str]:
    return await ScoreUser.get_uid_by_game(ev.user_id, ev.bot_id)


@sv_phantom_panel.on_regex(
    rf"^分析\s*(?P<char>{PATTERN})\s*(?P<type>面板|面包|🍞|card)$",
    block=True,
)
async def score_role_panel(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send(_format_msg("请先使用分析绑定UID后再查看面板", is_group), at_sender=is_group)

    alias_path = _get_alias_path()
    if not alias_path.exists():
        return await bot.send(_format_msg(f"别名文件不存在：{alias_path}", is_group), at_sender=is_group)

    raw_name = ev.regex_dict.get("char") if isinstance(ev.regex_dict, dict) else None
    if not raw_name:
        return await bot.send(_format_msg("请提供角色名", is_group), at_sender=is_group)

    role_name = alias_to_char_name_optional(alias_path, raw_name)
    if not role_name:
        return await bot.send(_format_msg("未找到对应的角色别名，请检查输入", is_group), at_sender=is_group)
    user_dir = get_user_dir(ev.user_id, uid)
    panel_path = user_dir / f"{role_name}.webp"
    if not panel_path.exists():
        return await bot.send(_format_msg("用户没有该角色面板图片，请使用分析指令获取", is_group), at_sender=is_group)
    with open(panel_path, "rb") as f:
        await bot.send(f.read())


@sv_phantom_panel.on_regex(
    rf"^分析\s*删除\s*(?P<char>{PATTERN})\s*(?P<type>面板|面包|🍞|card)$",
    block=True,
)
async def delete_role_panel(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send(_format_msg("请先使用分析绑定UID后再删除面板", is_group), at_sender=is_group)

    alias_path = _get_alias_path()
    if not alias_path.exists():
        return await bot.send(_format_msg(f"别名文件不存在：{alias_path}", is_group), at_sender=is_group)

    raw_name = ev.regex_dict.get("char") if isinstance(ev.regex_dict, dict) else None
    if not raw_name:
        return await bot.send(_format_msg("请提供角色名", is_group), at_sender=is_group)

    role_name = alias_to_char_name_optional(alias_path, raw_name)
    if not role_name:
        return await bot.send(_format_msg("未找到对应的角色别名，请检查输入", is_group), at_sender=is_group)

    user_dir = get_user_dir(ev.user_id, uid)
    panel_path = user_dir / f"{role_name}.webp"
    result_path = user_dir / "result.json"

    panel_exists = panel_path.exists()
    score_exists = False

    if panel_exists:
        try:
            panel_path.unlink()
            logger.info(f"已删除面板图片: {panel_path}")
        except Exception as e:
            logger.error(f"删除面板图片失败: {e}")
            return await bot.send(_format_msg(f"删除面板图片失败: {e}", is_group), at_sender=is_group)

    if result_path.exists():
        result_data = _load_result_data(result_path)
        if role_name in result_data:
            score_exists = True
            del result_data[role_name]
            _save_result_data(result_path, result_data)
            logger.info(f"已删除评分数据: {role_name}")

    if not panel_exists and not score_exists:
        return await bot.send(_format_msg(f"未找到{role_name}的面板数据", is_group), at_sender=is_group)

    msg_parts = []
    if panel_exists:
        msg_parts.append("面板图片")
    if score_exists:
        msg_parts.append("评分数据")

    msg = f"已成功删除{role_name}的" + "和".join(msg_parts)
    return await bot.send(_format_msg(msg, is_group), at_sender=is_group)


def _get_rating(total_score: float) -> str:
    """根据总分判断评级"""
    if total_score >= 210:
        return "SSS"
    elif total_score >= 195:
        return "SS"
    elif total_score >= 175:
        return "S"
    elif total_score >= 150:
        return "A"
    elif total_score >= 120:
        return "B"
    else:
        return "C"


def _format_msg(msg: str, is_group: bool) -> str:
    """根据聊天类型格式化消息"""
    if is_group:
        return " " + msg
    return msg


@sv_phantom_rank.on_fullmatch(("分析练度", "分析练度统计"), block=True)
async def score_phantom_rank(bot: Bot, ev: Event):
    uid = await _get_bound_uid(ev)
    if not uid:
        msg = "请先使用分析绑定UID后再查看练度统计"
        return await bot.send(msg, at_sender=False)

    user_dir = get_user_dir(ev.user_id, uid)
    result_path = user_dir / "result.json"
    result_data = _load_result_data(result_path)

    if not result_data:
        msg = "暂无评分数据，请先使用分析指令生成评分数据"
        return await bot.send(msg, at_sender=False)

    # 格式化输出：角色-总分-评级
    msg_lines = ["=== 鸣潮声骸练度统计 ==="]
    for role_name, scores in result_data.items():
        if isinstance(scores, list) and scores:
            total_score = sum(scores)
            rating = _get_rating(total_score)
            msg_lines.append(f"{role_name}: 总分{total_score:.2f} [{rating}]")
        else:
            msg_lines.append(f"{role_name}: 数据格式异常")

    msg = "\n".join(msg_lines)
    return await bot.send(msg, at_sender=False)

@sv_phantom_score.on_command(("评分", "查分", "pf"), block=True)
@sv_phantom_score.on_regex(
    (
        rf"({PATTERN})\s*(?:[cC](?:[oO][sS][tT])?\s*([134])|([134])\s*[cC](?:[oO][sS][tT])?)\s*({PATTERN})?$",
        rf"({PATTERN})(?:评分|查分)$",
    ),
    block=True,
)
async def score_phantom_handler(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    alias_error = _check_alias_path()
    if alias_error:
        await bot.send(_format_msg(alias_error, is_group), at_sender=is_group)
        return

    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send(_format_msg("请在发送命令的同时附带需要评分的声骸截图哦", is_group), at_sender=is_group)
        return

    try:
        images_b64 = await _encode_images(upload_images)
    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send(_format_msg("下载图片失败，请稍后再试。", is_group), at_sender=is_group)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send(_format_msg("图片处理失败，请稍后再试。", is_group), at_sender=is_group)
        return

    command_str = _build_command_str(ev.raw_text.strip())
    alias_path = _get_local_alias_path()
    if alias_path:
        command_str, _ = _replace_alias(command_str, alias_path)

    logger.info(f"准备发送评分请求，命令参数: {command_str}")

    headers = {
        "Authorization": f"Bearer {seconfig.get_config('xwtoken').data}",
        "Content-Type": "application/json",
    }
    payload = {
        "command_str": command_str,
        "images_base64": images_b64,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                seconfig.get_config("endpoint").data,
                headers=headers,
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()

            data = response.json()
            message = data.get("message")
            result_image_b64 = data.get("result_image_base64")

            logger.info(f"API 响应消息: {message}")

            if result_image_b64:
                result_image_data = base64.b64decode(result_image_b64)
                await bot.send(result_image_data)
            else:
                await bot.send(_format_msg(f"处理完成，但未能生成图片：\n{message}", is_group), at_sender=is_group)

    except httpx.HTTPStatusError as e:
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=is_group)

    except httpx.RequestError as e:
        logger.error(f"网络请求失败: {e}")
        await bot.send(_format_msg(f"连接评分服务器失败。\n错误: {e}", is_group), at_sender=is_group)

    except Exception as e:
        logger.exception(f"处理评分时发生未知错误: {e}")
        await bot.send(_format_msg(f"未知错误。联系小维\n错误详情: {e}", is_group), at_sender=is_group)


@sv_phantom_analysis.on_command(("分析",), block=True)
async def analyze_phantom_handler(bot: Bot, ev: Event):
    is_group = ev.group_id is not None
    uid = await _get_bound_uid(ev)
    if not uid:
        await bot.send(_format_msg("请先使用分析绑定UID后再进行分析", is_group), at_sender=is_group)
        return

    alias_error = _check_alias_path()
    if alias_error:
        await bot.send(_format_msg(alias_error, is_group), at_sender=is_group)
        return

    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send(_format_msg("请在发送命令的同时附带需要分析的声骸截图哦", is_group), at_sender=is_group)
        return

    try:
        images_b64 = await _encode_images(upload_images)
    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send(_format_msg("下载图片失败，请稍后再试。", is_group), at_sender=is_group)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send(_format_msg("图片处理失败，请稍后再试。", is_group), at_sender=is_group)
        return

    command_str = _build_command_str(ev.raw_text.strip())
    has_args = bool(ev.text.strip())
    alias_path = _get_local_alias_path()
    if alias_path:
        command_str, matched_name = _replace_alias(command_str, alias_path)

    char_info_path = _get_char_info_path(ev.user_id, uid)
    char_info = _load_char_info(char_info_path)
    user_name = char_info.get("用户名", "").strip()
    role_name = _extract_role_from_command(command_str)
    if role_name:
        alias_path = _get_alias_path()
        resolved_name = alias_to_char_name_optional(alias_path, role_name)
        role_name = matched_name or resolved_name or role_name
    role_info = char_info.get(matched_name, "").strip() if role_name else ""
    if role_info:
        command_str = f"{command_str} {role_info}".strip()

    logger.info(f"准备发送分析请求，命令参数: {command_str}, 是否有参数: {has_args}")

    headers = {
        "Authorization": f"Bearer {seconfig.get_config('xwtoken').data}",
        "Content-Type": "application/json",
    }
    user_data: Dict[str, str] = {"uid": uid}
    if user_name:
        user_data["user_name"] = user_name
    payload = {
        "command_str": command_str,
        "images_base64": images_b64,
        "user_data": user_data,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                seconfig.get_config("endpoint").data,
                headers=headers,
                json=payload,
                timeout=20.0,
            )
            response.raise_for_status()

            data = response.json()
            message = data.get("message")
            result_image_b64 = data.get("result_image_base64")
            score_results = data.get("score_results")
            matched_character = data.get("matched_character")

            logger.info(f"API 响应消息: {message}")

            if result_image_b64:
                result_image_data = base64.b64decode(result_image_b64)
                if role_name and has_args:
                    user_dir = get_user_dir(ev.user_id, uid)
                    user_dir.mkdir(parents=True, exist_ok=True)
                    panel_path = user_dir / f"{matched_character}.webp"
                    with open(panel_path, "wb") as f:
                        f.write(result_image_data)
                    if score_results is not None:
                        result_path = user_dir / "result.json"
                        result_data = _load_result_data(result_path)
                        result_data[role_name] = score_results
                        _save_result_data(result_path, result_data)
                await bot.send(result_image_data)
            else:
                await bot.send(_format_msg(f"处理完成，但未能生成图片：\n{message}", is_group), at_sender=is_group)

    except httpx.HTTPStatusError as e:
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=is_group)

    except httpx.RequestError as e:
        logger.error(f"网络请求失败: {e}")
        await bot.send(_format_msg(f"连接评分服务器失败。\n错误: {e}", is_group), at_sender=is_group)

    except Exception as e:
        logger.exception(f"处理分析时发生未知错误: {e}")
        await bot.send(_format_msg(f"未知错误。联系小维\n错误详情: {e}", is_group), at_sender=is_group)
