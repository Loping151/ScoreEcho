"""别名资源下载和管理"""
import httpx
from pathlib import Path

from gsuid_core.logger import logger

from .resource.RESOURCE_PATH import CHAR_ALIAS_PATH
from .resource import XW_CHAR_ALIAS_PATH


async def download_alias_from_url(url: str, target_path: Path) -> bool:
    """从 URL 下载别名文件

    Args:
        url: 下载 URL
        target_path: 目标路径

    Returns:
        是否成功
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            # 确保目标目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(response.text)

            logger.info(f"成功下载别名文件到: {target_path}")
            return True
    except Exception as e:
        logger.error(f"下载别名文件失败: {e}")
        return False


async def copy_alias_from_xwuid() -> bool:
    """从 XWUID 复制别名文件

    Returns:
        是否成功
    """
    if not XW_CHAR_ALIAS_PATH.exists():
        logger.warning(f"XWUID 别名文件不存在: {XW_CHAR_ALIAS_PATH}")
        return False

    try:
        # 确保目标目录存在
        CHAR_ALIAS_PATH.parent.mkdir(parents=True, exist_ok=True)

        # 复制文件
        import shutil
        shutil.copy2(XW_CHAR_ALIAS_PATH, CHAR_ALIAS_PATH)

        logger.info(f"成功从 XWUID 复制别名文件到: {CHAR_ALIAS_PATH}")
        return True
    except Exception as e:
        logger.error(f"复制别名文件失败: {e}")
        return False


async def ensure_alias_resource() -> bool:
    """确保别名资源存在

    优先级：
    1. 如果已存在，直接返回
    2. 尝试从 XWUID 复制
    3. 尝试从远程下载

    Returns:
        是否成功
    """
    # 如果已存在，直接返回
    if CHAR_ALIAS_PATH.exists():
        return True

    logger.info("别名文件不存在，尝试获取...")

    # 尝试从 XWUID 复制
    if await copy_alias_from_xwuid():
        return True

    # 尝试从远程下载
    # 使用小维的 1/2/3 号服务器
    urls = [
        "https://ww1.loping151.top/XutheringWavesUID/resource/map/alias/char_alias.json",
        "https://ww2.loping151.top/XutheringWavesUID/resource/map/alias/char_alias.json",
        "https://ww3.loping151.top/XutheringWavesUID/resource/map/alias/char_alias.json",
    ]

    for url in urls:
        if await download_alias_from_url(url, CHAR_ALIAS_PATH):
            return True

    logger.error("无法获取别名文件")
    return False


def check_alias_resource() -> bool:
    """检查别名资源是否存在

    Returns:
        是否存在
    """
    return CHAR_ALIAS_PATH.exists()
