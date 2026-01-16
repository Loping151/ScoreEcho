from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .help import get_help

sv_score_help = SV("ScoreEcho分析帮助", priority=2)


@sv_score_help.on_fullmatch(("分析帮助",), block=True)
async def send_score_help(bot: Bot, ev: Event):
    return await bot.send(await get_help(ev.user_pm))
