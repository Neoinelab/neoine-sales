"""Vendor 유스케이스: 조회, 생성·이름 변경·이름 규칙. Solution 관리는 폐지됐다.

삭제는 `test_vendor_delete.py`. 쓰기 유스케이스는 Vendor 행을 잠그고(`for_update`) 규칙을 판단한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.vendor.list_vendors import ListVendors
from app.application.vendor.register_vendor import RegisterVendor
from app.application.vendor.rename_vendor import RenameVendor
from app.domain.common.errors import InvalidValueError
from app.domain.vendor.errors import (
    DuplicateVendorNameError,
    VendorNotFoundError,
)
from app.domain.vendor.values import VendorId
from tests.factories_deal import seed_deal
from tests.factories_vendor import make_vendor
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


async def _names(uow: FakeUnitOfWork) -> list[str]:
    return [v.name for v in await uow.vendors.list()]


# --- ListVendors ---


async def test_list_vendors_returns_usage_without_solutions(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Vendor 목록은 소문자 이름순이고 Deal 수를 싣되 Solution 정보는 없다.

    테스트 코드: CL-045
    """
    # given: Zeta·sap·Oracle Vendor와 sap을 고른 Deal 2건이 있다
    sap = make_vendor("sap")
    oracle = make_vendor("Oracle")
    zeta = make_vendor("Zeta")
    for vendor in (zeta, sap, oracle):
        await uow.vendors.add(vendor)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id, solution="ITDR")
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id)

    # when: Vendor 목록을 읽는다
    result = await ListVendors(uow_factory).execute()

    # then: Oracle, sap, Zeta 순이고 사용 수 0, 2, 0이며 solutions 필드가 없다
    assert [u.vendor.name for u in result] == ["Oracle", "sap", "Zeta"]
    assert [u.usage_count for u in result] == [0, 2, 0]
    assert all(not hasattr(u, "solutions") for u in result)


async def test_list_vendors_does_not_count_deals_that_only_share_the_solution_text(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Vendor 사용 수는 그 Vendor를 고른 Deal 수이고 Solution 텍스트만 같은 Deal은 세지 않는다.

    테스트 코드: CL-046
    """
    # given: SAP·Oracle Vendor와 Solution 텍스트가 'SAP'인 Deal 2건(Oracle 선택·Vendor 없음)
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)
    await seed_deal(uow, code="20261016-A001", vendor_id=oracle.id, solution="SAP")
    await seed_deal(uow, code="20261016-A002", vendor_id=None, solution="SAP")

    # when: Vendor 목록을 읽는다
    result = await ListVendors(uow_factory).execute()

    # then: SAP는 0, Oracle은 1이다
    assert {u.vendor.name: u.usage_count for u in result} == {"SAP": 0, "Oracle": 1}


async def test_list_vendors_of_an_empty_system_is_empty(uow_factory: UnitOfWorkFactory) -> None:
    """Vendor가 없는 시스템의 목록은 빈 배열이다.

    테스트 코드: CL-045
    """
    # when: Vendor 목록을 읽는다
    result = await ListVendors(uow_factory).execute()
    # then: 빈 목록이다
    assert result == []


# --- RegisterVendor ---


async def test_register_vendor_returns_it_with_zero_usage(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Vendor를 등록하면 정규화된 이름·서버 시각·사용 수 0으로 저장되고 커밋된다.

    테스트 코드: CL-047
    """
    # when: '  SAP '를 등록한다
    result = await RegisterVendor(uow_factory, clock).execute("  SAP ")

    # then: 이름은 'SAP', 시각은 서버 시각, 사용 수 0, 커밋 1회, solutions 필드 없음
    stored = await uow.vendors.get(result.vendor.id)
    assert stored.name == "SAP"
    assert stored.created_at == stored.updated_at == clock.now()
    assert result.usage_count == 0
    assert not hasattr(result, "solutions")
    assert uow.commits == 1


async def test_register_vendor_with_existing_name_ignoring_case_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """대소문자만 다른 Vendor 이름은 중복으로 거절하고 저장하지 않는다.

    테스트 코드: CL-049
    """
    # given: 'SAP' Vendor가 있다
    await uow.vendors.add(make_vendor("SAP"))

    # when: ' sap '를 등록한다
    with pytest.raises(DuplicateVendorNameError):
        await RegisterVendor(uow_factory, clock).execute(" sap ")

    # then: 중복 오류이고 Vendor는 'SAP' 하나다
    assert await _names(uow) == ["SAP"]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", "Vendor 이름을 입력하세요."),
        ("   ", "Vendor 이름을 입력하세요."),
        ("a" * 101, "Vendor 이름은 100자 이내로 입력하세요."),
        ("  " + "a" * 101 + "  ", "Vendor 이름은 100자 이내로 입력하세요."),
    ],
    ids=["empty", "blank", "101-chars", "101-chars-padded"],
)
async def test_register_vendor_with_an_invalid_name_stores_nothing(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str, message: str
) -> None:
    """빈 이름·공백뿐·101자 이름은 Vendor 문구로 거절하고 저장하지 않는다.

    테스트 코드: CL-050
    """
    # when: 유효하지 않은 이름으로 등록한다
    with raises_with(InvalidValueError, message):
        await RegisterVendor(uow_factory, clock).execute(name)

    # then: 필수·길이 문구 오류이고 Vendor·커밋은 없다
    assert await _names(uow) == []
    assert uow.commits == 0


async def test_register_vendor_accepts_a_100_code_point_name_after_trimming(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """공백을 지운 뒤 100자(코드 포인트)인 Vendor 이름은 저장된다.

    테스트 코드: CL-050
    """
    # when: 앞뒤 공백이 붙은 이모지 100개 이름을 등록한다
    result = await RegisterVendor(uow_factory, clock).execute("  " + "😀" * 100 + "  ")

    # then: 공백이 지워진 이름으로 저장된다
    assert result.vendor.name == "😀" * 100
    assert await _names(uow) == ["😀" * 100]


@pytest.mark.parametrize("name", ["a\x00b", "\x00", "name\x00"], ids=["inside", "only", "trailing"])
async def test_register_vendor_with_a_nul_name_stores_nothing(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """NUL 문자가 든 Vendor 이름은 거절하고 저장하지 않는다.

    테스트 코드: CL-051
    """
    # when: NUL이 든 이름으로 등록한다
    with raises_with(InvalidValueError, "Vendor 이름에는 NUL 문자를 쓸 수 없습니다"):
        await RegisterVendor(uow_factory, clock).execute(name)

    # then: NUL 문구 오류이고 Vendor·커밋은 없다
    assert await _names(uow) == []
    assert uow.commits == 0


async def test_register_vendor_gives_a_later_vendor_a_larger_id(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """나중에 등록한 Vendor의 id가 더 크다.

    테스트 코드: CL-047
    """
    # when: SAP, Oracle을 차례로 등록한다
    first = await RegisterVendor(uow_factory, clock).execute("SAP")
    # then: 두 번째 id가 더 크고 정수다
    second = await RegisterVendor(uow_factory, clock).execute("Oracle")

    assert second.vendor.id > first.vendor.id
    assert type(first.vendor.id) is int


# --- RenameVendor ---


async def test_rename_vendor_returns_usage_count(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름 변경 결과에 사용 수가 실리고 수정 시각이 갱신된다.

    테스트 코드: CL-053
    """
    # given: Deal 2건이 고른 'SAP' Vendor가 있고 시간이 흘렀다
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)
    await seed_deal(uow, code="20261016-A001", vendor_id=sap.id)
    await seed_deal(uow, code="20261016-A002", vendor_id=sap.id)
    clock.advance(30)

    # when: 'SAP Korea'로 바꾼다
    result = await RenameVendor(uow_factory, clock).execute(sap.id, "SAP Korea")

    # then: 새 이름과 사용 수 2이고 updated_at이 서버 시각이다
    assert (result.vendor.name, result.usage_count) == ("SAP Korea", 2)
    assert (await uow.vendors.get(sap.id)).updated_at == clock.now()


async def test_rename_vendor_moves_it_in_the_list_order_to_follow_the_new_name(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름을 바꾸면 목록 순서가 새 이름을 따른다.

    테스트 코드: CL-053
    """
    # given: SAP, Oracle Vendor가 있다
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    # when: Oracle을 Zeta로 바꾼다
    await RenameVendor(uow_factory, clock).execute(oracle.id, "Zeta")

    # then: 목록은 SAP, Zeta 순이다
    assert [u.vendor.name for u in await ListVendors(uow_factory).execute()] == ["SAP", "Zeta"]


async def test_rename_vendor_to_its_own_name_in_other_case_is_allowed(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Vendor 자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CL-054
    """
    # given: 'Sap' Vendor가 있다
    sap = make_vendor("Sap")
    await uow.vendors.add(sap)

    # when: 'SAP'로 바꾼다
    result = await RenameVendor(uow_factory, clock).execute(sap.id, "SAP")

    # then: 이름이 'SAP'다
    assert result.vendor.name == "SAP"


async def test_rename_vendor_to_another_vendors_name_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """다른 Vendor의 이름으로 바꾸면 중복으로 거절하고 이름은 그대로다.

    테스트 코드: CL-055
    """
    # given: SAP·Oracle Vendor가 있다
    sap, oracle = make_vendor("SAP"), make_vendor("Oracle")
    await uow.vendors.add(sap)
    await uow.vendors.add(oracle)

    # when: SAP를 'ORACLE'로 바꾼다
    with pytest.raises(DuplicateVendorNameError):
        await RenameVendor(uow_factory, clock).execute(sap.id, "ORACLE")

    # then: 중복 오류이고 SAP 이름은 그대로다
    assert (await uow.vendors.get(sap.id)).name == "SAP"


async def test_rename_missing_vendor_is_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """없는 Vendor의 이름을 바꾸면 찾을 수 없음 오류다.

    테스트 코드: CL-057
    """
    # when·then: 없는 id의 이름을 바꾼다 → Vendor를 찾을 수 없음 오류다
    with pytest.raises(VendorNotFoundError):
        await RenameVendor(uow_factory, clock).execute(VendorId(new_id()), "X")


async def test_rename_vendor_with_a_blank_name_is_rejected(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """공백뿐인 새 Vendor 이름은 거절하고 이름은 그대로다.

    테스트 코드: CL-056
    """
    # given: 'SAP' Vendor가 있다
    sap = make_vendor("SAP")
    await uow.vendors.add(sap)

    # when: 공백뿐인 이름으로 바꾼다
    with raises_with(InvalidValueError, "Vendor 이름을 입력하세요."):
        await RenameVendor(uow_factory, clock).execute(sap.id, "  ")

    # then: 필수 문구 오류이고 이름은 그대로다
    assert (await uow.vendors.get(sap.id)).name == "SAP"
