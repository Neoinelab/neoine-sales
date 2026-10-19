"""Vendor·Solution 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

`Vendor`는 Aggregate Root이고 `Solution`은 그 안의 자식 엔티티다. 팩토리는 정규화·중복 검사를
거치지 않고 필드로 직접 만든다(규칙 자체를 검증하는 테스트가 팩토리에 기대지 않도록).
도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의 수집이 막히지 않게).
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from tests.factories import NOW

if TYPE_CHECKING:
    from collections.abc import Iterable

    from app.domain.vendor.entities import Solution, Vendor


def make_solution(name: str = "S/4HANA", **overrides: Any) -> Solution:  # noqa: ANN401
    """저장하지 않은 Solution. overrides: now, solution_id."""
    from app.domain.vendor.entities import Solution  # noqa: PLC0415 - 지연 import(모듈 설명 참고)
    from app.domain.vendor.values import SolutionId  # noqa: PLC0415

    now = overrides.pop("now", NOW)
    return Solution(
        id=overrides.pop("solution_id", SolutionId(uuid4())),
        name=name,
        created_at=now,
        updated_at=now,
    )


def make_vendor(
    name: str = "SAP",
    solutions: Iterable[str] = (),
    **overrides: Any,  # noqa: ANN401
) -> Vendor:
    """저장하지 않은 Vendor. solutions는 소속 Solution 이름들(입력 순서대로 담긴다).

    overrides: now, vendor_id.
    """
    from app.domain.vendor.entities import Vendor  # noqa: PLC0415
    from app.domain.vendor.values import VendorId  # noqa: PLC0415

    now = overrides.pop("now", NOW)
    return Vendor(
        id=overrides.pop("vendor_id", VendorId(uuid4())),
        name=name,
        solutions=[make_solution(solution, now=now) for solution in solutions],
        created_at=now,
        updated_at=now,
    )


async def store_vendor(
    repository: Any,  # noqa: ANN401 - VendorRepository(Fake 또는 SQL)
    name: str,
    solutions: Iterable[str] = (),
    **overrides: Any,  # noqa: ANN401
) -> Vendor:
    """Port 계약대로 저장한다: 빈 Vendor를 `add`한 뒤 Solution은 `update`로 맞춘다."""
    vendor = make_vendor(name, solutions, **overrides)
    await repository.add(make_vendor(name, (), vendor_id=vendor.id, now=vendor.created_at))
    if vendor.solutions:
        await repository.update(vendor)
    return vendor
