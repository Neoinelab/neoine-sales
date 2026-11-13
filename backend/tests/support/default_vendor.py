"""기본 Deal이 가리키는 Vendor(Vendor는 Deal의 필수 값이다, DE-R7).

`make_deal_details`의 기본 `vendor_id`가 이 Vendor다. Deal을 저장소에 넣기 전에
`ensure_default_vendor`로 이 Vendor를 (없으면) 만든다. 이름은 다른 테스트의 "SAP"와 겹치지
않게 한다.
"""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Final

from tests.support.ids import new_id

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.vendor.values import VendorId

DEFAULT_VENDOR_ID: Final = new_id()
DEFAULT_VENDOR_NAME: Final = "기본 Vendor"


def default_vendor_id() -> VendorId:
    """기본 Deal의 Vendor id(타입 표시용)."""
    from app.domain.vendor.values import VendorId  # noqa: PLC0415 - 지연 import

    return VendorId(DEFAULT_VENDOR_ID)


async def ensure_default_vendor(vendors: Any) -> None:  # noqa: ANN401 - VendorRepository
    """기본 Vendor가 저장소에 없으면 만든다(있으면 그대로)."""
    from app.domain.vendor.errors import VendorNotFoundError  # noqa: PLC0415
    from tests.factories_vendor import make_vendor  # noqa: PLC0415

    try:
        await vendors.get(default_vendor_id())
    except VendorNotFoundError:
        await vendors.add(make_vendor(DEFAULT_VENDOR_NAME, vendor_id=default_vendor_id()))


@asynccontextmanager
async def rolled_back_session_with_vendor(url: URL) -> AsyncIterator[AsyncSession]:
    """`rolled_back_session`에 기본 Deal의 Vendor(`DEFAULT_VENDOR_ID`)를 미리 넣어 둔 세션.

    Deal은 Vendor가 필수(NOT NULL + FK)라, 기본 Deal 팩토리를 쓰는 SQL case는 이 세션으로 시작한다.
    Vendor 목록·삭제를 검사하는 case(`vendor_case`)는 쓰지 않는다.
    """
    from app.infra.db.vendor_repository import SqlVendorRepository  # noqa: PLC0415
    from tests.support.database import rolled_back_session  # noqa: PLC0415

    async with rolled_back_session(url) as session:
        await ensure_default_vendor(SqlVendorRepository(session))
        yield session
