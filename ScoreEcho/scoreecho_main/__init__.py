import base64
import httpx
from io import BytesIO

from PIL import Image

from gsuid_core.sv import SV, get_plugin_available_prefix
from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.logger import logger

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

from .config import seconfig

sv_phantom_scorer = SV("鸣潮声骸评分")
PREFIX = get_plugin_available_prefix("ScoreEcho")

@sv_phantom_scorer.on_command(('评分'))
async def score_phantom_handler(bot: Bot, ev: Event):
    """
    处理声骸评分请求，调用外部 API 并返回结果。
    """
    upload_images = await get_image(ev)
    if not upload_images:
        await bot.send("请在发送命令的同时附带需要评分的声骸截图哦", at_sender=True)
        return

    images_b64 = []
    try:
        async with httpx.AsyncClient() as client:
            for image_url in upload_images:
                # 下载图片
                resp = await client.get(image_url)
                resp.raise_for_status()
                image_bytes = resp.content

                MAX_SIZE_BYTES = 2 * 1024 * 1024  # 1MB size limit

                with Image.open(BytesIO(image_bytes)) as img:
                    # Convert to RGB if it's not, as RGBA/P etc. can't be saved as JPEG/WEBP directly
                    if img.mode not in ("RGB"):
                        img = img.convert("RGB")

                    output_buffer = BytesIO()
                    quality = 100  # Initial quality
                    
                    while quality > 10:
                        output_buffer.seek(0)  # Reset buffer to the beginning
                        output_buffer.truncate() # Clear the buffer
                        img.save(output_buffer, format="WEBP", quality=quality)
                        if output_buffer.tell() < MAX_SIZE_BYTES:
                            break
                        quality -= 5 # Decrease quality
                    
                    compressed_image_bytes = output_buffer.getvalue()

                images_b64.append(base64.b64encode(compressed_image_bytes).decode('utf-8'))

    except httpx.RequestError as e:
        logger.error(f"下载图片失败: {e}")
        await bot.send("下载图片失败，请稍后再试。", at_sender=True)
        return
    except Exception as e:
        logger.error(f"图片处理失败: {e}")
        await bot.send("图片处理失败，请稍后再试。", at_sender=True)
        return

    # 3. 准备请求头和请求体
    # ev.text 包含了用户发送的完整命令，例如 "评分 忌炎 4c"
    command_str = ev.text.strip().split("评分", 1)[-1].strip()
    
    headers = {
        "Authorization": f"Bearer {seconfig.get_config('xwtoken').data[0]}",
        "Content-Type": "application/json"
    }
    payload = {
        "command_str": command_str,
        "images_base64": images_b64  # 使用包含所有图片base64的列表
    }
    
    # 4. 使用 httpx 异步发送 POST 请求
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ':'.join(seconfig.get_config('endpoint').data),
                headers=headers, 
                json=payload, 
                timeout=20.0  # Increased timeout slightly for potentially larger requests
            )
            # 检查 HTTP 错误 (例如 404, 500)
            response.raise_for_status()

            # 5. 处理 API 响应
            data = response.json()
            message = data.get("message")
            result_image_b64 = data.get("result_image_base64")

            logger.info(f"API 响应消息: {message}")

            if result_image_b64:
                result_image_data = base64.b64decode(result_image_b64)
                await bot.send(result_image_data)
            else:
                # 如果没有返回图片，则发送服务器返回的文本消息
                await bot.send(f"处理完成，但未能生成图片：\n{message}", at_sender=True)

    except httpx.HTTPStatusError as e:
        # 处理 HTTP 错误，例如 401 Unauthorized 或 500 Internal Server Error
        error_msg = f"API 请求失败，服务器返回错误码: {e.response.status_code}"
        try:
            # 尝试解析服务器返回的错误详情
            error_detail = e.response.json().get("detail", "无详细信息")
            error_msg += f"\n错误信息: {error_detail}"
        except Exception:
            error_msg += f"\n原始响应: {e.response.text}"
        logger.error(error_msg)
        await bot.send(error_msg, at_sender=True)
        
    except httpx.RequestError as e:
        # 处理网络层面的错误，例如连接超时、无法解析域名等
        logger.error(f"网络请求失败: {e}")
        await bot.send(f"连接评分服务器失败。\n错误: {e}", at_sender=True)
        
    except Exception as e:
        # 处理其他未知错误，例如 JSON 解析失败
        logger.exception(f"处理评分时发生未知错误: {e}")
        await bot.send(f"未知错误。联系小维\n错误详情: {e}", at_sender=True)