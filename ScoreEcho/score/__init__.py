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

from ..config.config import seconfig
from ..utils.database.models import ScoreUser
from ..utils.resource import XW_CHAR_ALIAS_PATH, get_user_dir
from ..utils.charlist_draw import draw_charlist_image

try:
    from ....XutheringWavesUID.XutheringWavesUID.utils.char_info_utils import PATTERN
    from ....XutheringWavesUID.XutheringWavesUID.utils.name_convert import (
        alias_to_char_name_optional,
    )
except Exception:  # pragma: no cover - fallback if dependency missing
    PATTERN = r"[\u4e00-\u9fa5a-zA-Z0-9]{1,15}"
    alias_to_char_name_optional = None


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
    alias_path = _get_local_alias_path()
    if not alias_path or not alias_path.exists():
        return f"别名文件不存在：{alias_path}"
    return None


def _replace_alias(command_str: str, alias_path: Path) -> str:
    try:
        with open(alias_path, "r", encoding="utf-8") as f:
            alias_data = json.load(f)
        for char_name, alias_list in alias_data.items():
            for alias in alias_list:
                if alias in command_str:
                    command_str = command_str.replace(alias, char_name)
                    logger.info(f"替换别名: {alias} -> {char_name}")
                    break
    except Exception as e:
        logger.error(f"加载本地别名文件失败: {e}")
    return command_str


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
    parts = command_str.strip().split()
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
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send("请先使用分析绑定UID后再查看面板", at_sender=True)
    if not XW_CHAR_ALIAS_PATH.exists():
        return await bot.send(f"别名文件不存在：{XW_CHAR_ALIAS_PATH}", at_sender=True)
    raw_name = ev.regex_dict.get("char") if isinstance(ev.regex_dict, dict) else None
    if not raw_name:
        return await bot.send("请提供角色名", at_sender=True)
    if alias_to_char_name_optional is None:
        return await bot.send("别名解析不可用，请检查资源", at_sender=True)
    role_name = alias_to_char_name_optional(raw_name)
    if not role_name:
        return await bot.send("未找到对应的角色别名，请检查输入", at_sender=True)
    user_dir = get_user_dir(ev.user_id, uid)
    panel_path = user_dir / f"{role_name}.webp"
    if not panel_path.exists():
        return await bot.send("用户没有该角色面板图片，请使用分析指令获取", at_sender=True)
    with open(panel_path, "rb") as f:
        await bot.send(f.read())


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

from ..config.config import seconfig
from ..utils.database.models import ScoreUser
from ..utils.resource import XW_CHAR_ALIAS_PATH, get_user_dir
from ..utils.charlist_draw import draw_charlist_image

try:
    from ....XutheringWavesUID.XutheringWavesUID.utils.char_info_utils import PATTERN
    from ....XutheringWavesUID.XutheringWavesUID.utils.name_convert import (
        alias_to_char_name_optional,
    )
except Exception:  # pragma: no cover - fallback if dependency missing
    PATTERN = r"[\u4e00-\u9fa5a-zA-Z0-9]{1,15}"
    alias_to_char_name_optional = None


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
    alias_path = _get_local_alias_path()
    if not alias_path or not alias_path.exists():
        return f"别名文件不存在：{alias_path}"
    return None


def _replace_alias(command_str: str, alias_path: Path) -> str:
    try:
        with open(alias_path, "r", encoding="utf-8") as f:
            alias_data = json.load(f)
        for char_name, alias_list in alias_data.items():
            for alias in alias_list:
                if alias in command_str:
                    command_str = command_str.replace(alias, char_name)
                    logger.info(f"替换别名: {alias} -> {char_name}")
                    break
    except Exception as e:
        logger.error(f"加载本地别名文件失败: {e}")
    return command_str


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
    parts = command_str.strip().split()
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
    uid = await _get_bound_uid(ev)
    if not uid:
        return await bot.send("请先使用分析绑定UID后再查看面板", at_sender=True)
    if not XW_CHAR_ALIAS_PATH.exists():
        return await bot.send(f"别名文件不存在：{XW_CHAR_ALIAS_PATH}", at_sender=True)
    raw_name = ev.regex_dict.get("char") if isinstance(ev.regex_dict, dict) else None
    if not raw_name:
        return await bot.send("请提供角色名", at_sender=True)
    if alias_to_char_name_optional is None:
        return await bot.send("别名解析不可用，请检查资源", at_sender=True)
    role_name = alias_to_char_name_optional(raw_name)
    if not role_name:
        return await bot.send("未找到对应的角色别名，请检查输入", at_sender=True)
    user_dir = get_user_dir(ev.user_id, uid)
    panel_path = user_dir / f"{role_name}.webp"
    if not panel_path.exists():
        return await bot.send("用户没有该角色面板图片，请使用分析指令获取", at_sender=True)
    with open(panel_path, "rb") as f:
        await bot.send(f.read())


@sv_phantom_rank.on_fullmatch(("分析练度", "分析练度统计"), block=True)
async def score_phantom_rank(bot: Bot, ev: Event):
    # TODO: 恢复图像输出时使用
    # image_bytes = draw_charlist_image(result_data)
    # return await bot.send(image_bytes)
    return await bot.send("施工中，当前仅展示文本：{}", at_sender=True)


@sv_phantom_score.on_command(("评分", "查分"), block=True)
@sv_phantom_score.on_regex(
    (
        rf"({PATTERN})\s*(?:[cC](?:[oO][sS][tT])?\s*([134])|([134])\s*[cC](?:[oO][sS][tT])?)\s*({PATTERN})?$",
        rf"({PATTERN})(?:评分|查分)$",
    ),
    block=True,
)
async def score_phantom_handler(bot: Bot, ev: Event):
    alias_error = _check_alias_path()
    if alias_error:
        await bot.send(alias_error, at_sender=True)
        return

    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send("请在发送命令的同时附带需要评分的声骸截图哦", at_sender=True)
        return

    try:
        images_b64 = await _encode_images(upload_images)
    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send("下载图片失败，请稍后再试。", at_sender=True)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send("图片处理失败，请稍后再试。", at_sender=True)
        return

    command_str = _build_command_str(ev.raw_text.strip())
    alias_path = _get_local_alias_path()
    if alias_path:
        command_str = _replace_alias(command_str, alias_path)

    logger.info(f"准备发送评分请求，命令参数: {command_str}")

    headers = {
        "Authorization": f"Bearer {seconfig.get_config('xwtoken').data}",
        "Content-Type": "application/json",
    }
    payload = {
        "command_str": command_str,
        "images_base64": images_b64,
    }

    score_results = None
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
                await bot.send(f"处理完成，但未能生成图片：\n{message}", at_sender=True)

    except httpx.HTTPStatusError as e:
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=True)

    except httpx.RequestError as e:
        logger.error(f"网络请求失败: {e}")
        await bot.send(f"连接评分服务器失败。\n错误: {e}", at_sender=True)

    except Exception as e:
        logger.exception(f"处理评分时发生未知错误: {e}")
        await bot.send(f"未知错误。联系小维\n错误详情: {e}", at_sender=True)


@sv_phantom_analysis.on_command(("分析",), block=True)
async def analyze_phantom_handler(bot: Bot, ev: Event):
    uid = await _get_bound_uid(ev)
    if not uid:
        await bot.send("请先使用分析绑定UID后再进行分析", at_sender=True)
        return

    alias_error = _check_alias_path()
    if alias_error:
        await bot.send(alias_error, at_sender=True)
        return

    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send("请在发送命令的同时附带需要分析的声骸截图哦", at_sender=True)
        return

    try:
        images_b64 = await _encode_images(upload_images)
    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send("下载图片失败，请稍后再试。", at_sender=True)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send("图片处理失败，请稍后再试。", at_sender=True)
        return

    command_str = _build_command_str(ev.raw_text.strip())
    alias_path = _get_local_alias_path()
    if alias_path:
        command_str = _replace_alias(command_str, alias_path)

    char_info_path = _get_char_info_path(ev.user_id, uid)
    char_info = _load_char_info(char_info_path)
    user_name = char_info.get("用户名", "").strip()
    role_name = _extract_role_from_command(command_str.split("换")[0].replace("分析", "").strip())
    if role_name and alias_to_char_name_optional and XW_CHAR_ALIAS_PATH.exists():
        role_name = alias_to_char_name_optional(role_name) or role_name
    role_info = char_info.get(role_name, "").strip() if role_name else ""
    if role_info:
        command_str = f"{command_str} {role_info}".strip()

    logger.info(f"准备发送分析请求，命令参数: {command_str}")

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

            logger.info(f"API 响应消息: {message}")

            if result_image_b64:
                result_image_data = base64.b64decode(result_image_b64)
                if role_name:
                    user_dir = get_user_dir(ev.user_id, uid)
                    user_dir.mkdir(parents=True, exist_ok=True)
                    panel_path = user_dir / f"{role_name}.webp"
                    with open(panel_path, "wb") as f:
                        f.write(result_image_data)
                    if score_results is not None:
                        result_path = user_dir / "result.json"
                        result_data = _load_result_data(result_path)
                        result_data[role_name] = score_results
                        _save_result_data(result_path, result_data)
                else:
                    await bot.send("未设置角色名，无法保存面板，请先使用设置角色", at_sender=True)
                await bot.send(result_image_data)
            else:
                await bot.send(f"处理完成，但未能生成图片：\n{message}", at_sender=True)

    except httpx.HTTPStatusError as e:
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=True)

    except httpx.RequestError as e:
        logger.error(f"网络请求失败: {e}")
        await bot.send(f"连接评分服务器失败。\n错误: {e}", at_sender=True)

    except Exception as e:
        logger.exception(f"处理分析时发生未知错误: {e}")
        await bot.send(f"未知错误。联系小维\n错误详情: {e}", at_sender=True)


@sv_phantom_score.on_command(("评分", "查分"), block=True)
@sv_phantom_score.on_regex(
    (
        rf"({PATTERN})\s*(?:[cC](?:[oO][sS][tT])?\s*([134])|([134])\s*[cC](?:[oO][sS][tT])?)\s*({PATTERN})?$",
        rf"({PATTERN})(?:评分|查分)$",
    ),
    block=True,
)
async def score_phantom_handler(bot: Bot, ev: Event):
    alias_error = _check_alias_path()
    if alias_error:
        await bot.send(alias_error, at_sender=True)
        return

    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send("请在发送命令的同时附带需要评分的声骸截图哦", at_sender=True)
        return

    try:
        images_b64 = await _encode_images(upload_images)
    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send("下载图片失败，请稍后再试。", at_sender=True)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send("图片处理失败，请稍后再试。", at_sender=True)
        return

    command_str = _build_command_str(ev.raw_text.strip())
    alias_path = _get_local_alias_path()
    if alias_path:
        command_str = _replace_alias(command_str, alias_path)

    logger.info(f"准备发送评分请求，命令参数: {command_str}")

    headers = {
        "Authorization": f"Bearer {seconfig.get_config('xwtoken').data}",
        "Content-Type": "application/json",
    }
    payload = {
        "command_str": command_str,
        "images_base64": images_b64,
    }

    score_results = None
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
                await bot.send(f"处理完成，但未能生成图片：\n{message}", at_sender=True)

    except httpx.HTTPStatusError as e:
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=True)

    except httpx.RequestError as e:
        logger.error(f"网络请求失败: {e}")
        await bot.send(f"连接评分服务器失败。\n错误: {e}", at_sender=True)

    except Exception as e:
        logger.exception(f"处理评分时发生未知错误: {e}")
        await bot.send(f"未知错误。联系小维\n错误详情: {e}", at_sender=True)


@sv_phantom_analysis.on_command(("分析",), block=True)
async def analyze_phantom_handler(bot: Bot, ev: Event):
    uid = await _get_bound_uid(ev)
    if not uid:
        await bot.send("请先使用分析绑定UID后再进行分析", at_sender=True)
        return

    alias_error = _check_alias_path()
    if alias_error:
        await bot.send(alias_error, at_sender=True)
        return

    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send("请在发送命令的同时附带需要分析的声骸截图哦", at_sender=True)
        return

    try:
        images_b64 = await _encode_images(upload_images)
    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send("下载图片失败，请稍后再试。", at_sender=True)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send("图片处理失败，请稍后再试。", at_sender=True)
        return

    command_str = _build_command_str(ev.raw_text.strip())
    alias_path = _get_local_alias_path()
    if alias_path:
        command_str = _replace_alias(command_str, alias_path)

    char_info_path = _get_char_info_path(ev.user_id, uid)
    char_info = _load_char_info(char_info_path)
    user_name = char_info.get("用户名", "").strip()
    role_name = _extract_role_from_command(command_str.split("换")[0].replace("分析", "").strip())
    if role_name and alias_to_char_name_optional and XW_CHAR_ALIAS_PATH.exists():
        role_name = alias_to_char_name_optional(role_name) or role_name
    role_info = char_info.get(role_name, "").strip() if role_name else ""
    if role_info:
        command_str = f"{command_str} {role_info}".strip()

    logger.info(f"准备发送分析请求，命令参数: {command_str}")

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

            logger.info(f"API 响应消息: {message}")

            if result_image_b64:
                result_image_data = base64.b64decode(result_image_b64)
                if role_name:
                    user_dir = get_user_dir(ev.user_id, uid)
                    user_dir.mkdir(parents=True, exist_ok=True)
                    panel_path = user_dir / f"{role_name}.webp"
                    with open(panel_path, "wb") as f:
                        f.write(result_image_data)
                    if score_results is not None:
                        result_path = user_dir / "result.json"
                        result_data = _load_result_data(result_path)
                        result_data[role_name] = score_results
                        _save_result_data(result_path, result_data)
                else:
                    await bot.send("未设置角色名，无法保存面板，请先使用设置角色", at_sender=True)
                await bot.send(result_image_data)
            else:
                await bot.send(f"处理完成，但未能生成图片：\n{message}", at_sender=True)

    except httpx.HTTPStatusError as e:
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=True)

    except httpx.RequestError as e:
        logger.error(f"网络请求失败: {e}")
        await bot.send(f"连接评分服务器失败。\n错误: {e}", at_sender=True)

    except Exception as e:
        logger.exception(f"处理分析时发生未知错误: {e}")
        await bot.send(f"未知错误。联系小维\n错误详情: {e}", at_sender=True)
