from typing import Dict, List, Optional
from pathlib import Path

from msgspec import json as msgjson

from gsuid_core.logger import logger

# 正则模式 - 从 XutheringWavesUID 复制
PATTERN = r"[\u4e00-\u9fa5a-zA-Z0-9\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U00003200-\U000032FF-—·()（）]{1,15}"

# 全局变量
char_alias_data: Dict[str, List[str]] = {}
_data_loaded = False
_auto_download_enabled = True  # 是否自动下载别名资源


def load_alias_data(alias_path: Path):
    """加载别名数据"""
    global char_alias_data

    if alias_path.exists():
        try:
            with open(alias_path, "r", encoding="UTF-8") as f:
                char_alias_data = msgjson.decode(f.read(), type=Dict[str, List[str]])
        except Exception as e:
            logger.exception(f"读取角色别名失败 {alias_path} - {e}")
            char_alias_data = {}
    else:
        logger.warning(f"别名文件不存在: {alias_path}")
        # 如果启用了自动下载，尝试下载
        if _auto_download_enabled:
            logger.info("尝试自动下载别名资源...")
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果在异步环境中，创建任务
                    asyncio.create_task(_async_download_and_load(alias_path))
                else:
                    # 如果不在异步环境中，直接运行
                    asyncio.run(_async_download_and_load(alias_path))
            except Exception as download_err:
                logger.error(f"自动下载别名资源失败: {download_err}")
        char_alias_data = {}


async def _async_download_and_load(alias_path: Path):
    """异步下载并加载别名数据"""
    from .alias_resource import ensure_alias_resource
    success = await ensure_alias_resource()
    if success:
        # 重新加载
        global char_alias_data
        try:
            with open(alias_path, "r", encoding="UTF-8") as f:
                char_alias_data = msgjson.decode(f.read(), type=Dict[str, List[str]])
            logger.info("别名资源下载并加载成功")
        except Exception as e:
            logger.error(f"加载下载的别名资源失败: {e}")
    else:
        logger.warning("别名资源下载失败")


def ensure_data_loaded(alias_path: Path, force: bool = False):
    """确保所有数据已加载

    Args:
        alias_path: 别名文件路径
        force: 如果为 True，强制重新加载所有数据，即使已经加载过
    """
    global _data_loaded

    if _data_loaded and not force:
        return

    load_alias_data(alias_path)
    _data_loaded = True


def alias_to_char_name_optional(alias_path: Path, char_name: Optional[str]) -> Optional[str]:
    """将别名转换为角色名（可选版本，返回 None 如果未找到）

    Args:
        alias_path: 别名文件路径
        char_name: 角色名或别名

    Returns:
        标准角色名，如果未找到则返回 None
    """
    ensure_data_loaded(alias_path)
    if not char_name:
        return None
    for key, aliases in char_alias_data.items():
        if char_name == key or char_name in aliases:
            return key
    for i in char_alias_data:
        if (char_name in i) or (char_name in char_alias_data[i]):
            return i
    return None
