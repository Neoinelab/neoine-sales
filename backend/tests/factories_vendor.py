"""Vendor 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

팩토리는 정규화·중복 검사를 거치지 않고 필드로 직접 만든다(규칙 자체를 검증하는 테스트가
팩토리에 기대지 않도록). Solution은 Vendor 관리 대상이 아니라 Deal의 자유 텍스트이므로
여기에 없다.
도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이 막히지 않게).
"""

from typing import TYPE_CHECKING, Any

from tests.factories import NOW
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.domain.vendor.entities import Vendor


def make_vendor(name: str = "SAP", **overrides: Any) -> Vendor:  # noqa: ANN401
    """저장하지 않은 Vendor. overrides: now, vendor_id."""
    from app.domain.vendor.entities import Vendor  # noqa: PLC0415 - 지연 import(모듈 설명 참고)
    from app.domain.vendor.values import VendorId  # noqa: PLC0415

    now = overrides.pop("now", NOW)
    return Vendor(
        id=overrides.pop("vendor_id", VendorId(new_id())),
        name=name,
        created_at=now,
        updated_at=now,
    )


async def store_vendor(
    repository: Any,  # noqa: ANN401 - VendorRepository(Fake 또는 SQL)
    name: str,
    **overrides: Any,  # noqa: ANN401
) -> Vendor:
    """Port 계약대로 `add`로 저장한다."""
    vendor = make_vendor(name, **overrides)
    await repository.add(vendor)
    return vendor
