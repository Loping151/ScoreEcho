from typing import Any, Dict, Optional

from sqlmodel import Field

from gsuid_core.utils.database.base_models import Bind
from gsuid_core.webconsole.mount_app import GsAdminModel, PageSchema, site


class ScoreUser(Bind, table=True):
    __table_args__: Dict[str, Any] = {"extend_existing": True}
    __tablename__ = "ScoreEcho"
    uid: Optional[str] = Field(default=None, title="ScoreEcho UID")


@site.register_admin
class ScoreUserAdmin(GsAdminModel):
    pk_name = "id"
    page_schema = PageSchema(
        label="ScoreEcho用户管理",
        icon="fa fa-users",
    )  # type: ignore

    model = ScoreUser
