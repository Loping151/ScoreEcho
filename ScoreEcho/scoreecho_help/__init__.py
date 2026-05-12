from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from .help import get_help

sv_score_help = SV("ScoreEcho分析帮助", priority=2)


@sv_score_help.on_fullmatch(
    ("分析帮助", "分析幫助"),
    block=True,
    to_ai="""返回 ScoreEcho（鸣潮声骸评分 / 练度分析）插件的命令帮助图。

当用户问「分析帮助 / 声骸评分怎么用 / 练度分析帮助」时调用。

Args:
    text: 无需参数。
""",
)
async def send_score_help(bot: Bot, ev: Event):
    return await bot.send(await get_help(ev.user_pm))
