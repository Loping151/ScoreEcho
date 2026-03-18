from typing import Any, Dict, Type, TypeVar, Optional

from sqlmodel import Field, select
from sqlalchemy.ext.asyncio import AsyncSession

from gsuid_core.utils.database.base_models import Bind, BaseIDModel, with_session
from gsuid_core.webconsole.mount_app import GsAdminModel, PageSchema, site


class ScoreUser(Bind, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    __tablename__ = "ScoreEcho"
    uid: Optional[str] = Field(default=None, title="ScoreEcho UID")


T_ScoreLangSettings = TypeVar("T_ScoreLangSettings", bound="ScoreLangSettings")


class ScoreLangSettings(BaseIDModel, table=True):
    """用户语言设置表"""

    __tablename__ = "ScoreLangSettings"
    __table_args__: Dict[str, Any] = {"extend_existing": True}

    user_id: str = Field(default="", title="账号", unique=True)
    lang: str = Field(default="", title="语言设置")

    @classmethod
    @with_session
    async def get_lang(
        cls: Type[T_ScoreLangSettings],
        session: AsyncSession,
        user_id: str,
    ) -> str:
        result = await session.execute(
            select(cls).where(cls.user_id == user_id)
        )
        record = result.scalars().first()
        return record.lang if record else ""

    @classmethod
    @with_session
    async def set_lang(
        cls: Type[T_ScoreLangSettings],
        session: AsyncSession,
        user_id: str,
        lang: str,
    ) -> None:
        result = await session.execute(
            select(cls).where(cls.user_id == user_id)
        )
        record = result.scalars().first()
        if record:
            record.lang = lang
        else:
            session.add(cls(user_id=user_id, lang=lang))


@site.register_admin
class ScoreUserAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="ScoreEcho用户管理",
        icon="fa fa-users",
    )  # type: ignore

    model = ScoreUser
