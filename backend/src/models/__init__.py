"""ORM-Modelle.

Neue Modelle hier importieren, damit `Base.metadata` sie kennt und Alembics
`--autogenerate` sie erfasst.
"""

from .attachment import Attachment
from .label import Label, page_label
from .page import Page
from .page_link import PageLink
from .page_version import PageVersion
from .space import Space
from .space_permission import RANG, Recht, SpacePermission
from .user import User
from .user_session import UserSession

__all__ = [
    "RANG",
    "Attachment",
    "Label",
    "Page",
    "PageLink",
    "PageVersion",
    "Recht",
    "Space",
    "SpacePermission",
    "User",
    "UserSession",
    "page_label",
]
