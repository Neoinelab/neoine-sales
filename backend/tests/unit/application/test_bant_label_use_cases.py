"""BANT Label 유스케이스: 조회, 생성, 이름 변경. 삭제는 별도 모듈.

쓰기 유스케이스는 같은 구분의 행을 잠그고(`list(category, for_update=True)`) 중복을 판단한다.
Label 사용 수는 P0에 Deal 연결이 없어 Fake deals에 주입한 값으로 검증한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.bant.list_labels import ListBantLabels
from app.application.bant.register_label import RegisterBantLabel
from app.application.bant.rename_label import RenameBantLabel
from app.domain.bant.errors import BantLabelNotFoundError, DuplicateLabelNameError
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.common.errors import InvalidValueError
from tests.factories_auth import make_user
from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.value_objects import UserId
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

DEFAULT_ORDER = [(category, name) for category, names in DEFAULT_LABELS.items() for name in names]


async def _creator(uow: FakeUnitOfWork, login_id: str = "kim") -> UserId:
    user = make_user(login_id)
    await uow.users.add(user)
    return user.id


async def _names(uow: FakeUnitOfWork, category: BantCategory) -> list[str]:
    return [label.name for label in await uow.bant_labels.list(category)]


# --- ListBantLabels ---


async def test_list_labels_returns_the_23_defaults_in_seed_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """기본 Label 23개가 구분·시드 순서로 나오고 모두 기본 표시이며 만든 사람이 없다.

    테스트 코드: CL-001
    """
    # when: Label 목록을 읽는다
    result = await ListBantLabels(uow_factory).execute()

    # then: 23개가 구분 선언 순·시드 순서이고 모두 기본·만든 사람 없음
    assert [(u.label.category.value, u.label.name) for u in result] == DEFAULT_ORDER
    assert len(result) == 23
    assert all(u.label.is_default and u.label.created_by_user_id is None for u in result)


async def test_list_labels_puts_custom_labels_after_defaults_sorted_by_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """직접 만든 Label은 그 구분의 기본 Label 뒤에 소문자 이름 코드 포인트 순으로 나온다.

    테스트 코드: CL-002
    """
    # given: need 구분에 '나중에', '가장 먼저', 'Zeta', 'alpha'를 차례로 만들었다
    creator = await _creator(seeded)
    register = RegisterBantLabel(uow_factory, clock)
    for name in ("나중에", "가장 먼저", "Zeta", "alpha"):
        await register.execute(BantCategory.NEED, name, creator)

    # when: Label 목록을 읽는다
    result = await ListBantLabels(uow_factory).execute()

    # then: need는 기본 Label 뒤에 alpha, Zeta, 가장 먼저, 나중에 순이다

    need = [u.label.name for u in result if u.label.category is BantCategory.NEED]
    assert need == [*DEFAULT_LABELS["need"], "alpha", "Zeta", "가장 먼저", "나중에"]


async def test_list_labels_reports_usage_counts_per_label(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """목록의 사용 수는 Label별로 Deal이 선택한 수이고 안 쓰면 0이다.

    테스트 코드: CL-003
    """
    # given: '예산 없음'을 Deal 4건이 선택했다고 집계된다
    used = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    seeded.deals.bant_label_counts = {used.id: 4}

    # when: Label 목록을 읽는다
    result = await ListBantLabels(uow_factory).execute()

    # then: 그 Label만 4이고 합계도 4다
    assert {u.label.id: u.usage_count for u in result}[used.id] == 4
    assert sum(u.usage_count for u in result) == 4


# --- RegisterBantLabel ---


async def test_register_label_records_the_creator_and_is_not_default(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """등록한 Label은 직접 만든 항목이고 만든 사람·서버 시각이 기록되며 사용 수는 0이다.

    테스트 코드: CL-004
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: timeline에 '분기 내 구매'를 등록한다
    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.TIMELINE, "분기 내 구매", creator
    )

    # then: 저장된 Label은 기본이 아니고 만든 사람·시각이 기록되고 사용 수 0이다
    stored = await seeded.bant_labels.get(result.label.id)
    assert (stored.category, stored.name) == (BantCategory.TIMELINE, "분기 내 구매")
    assert stored.is_default is False
    assert stored.default_order is None
    assert stored.created_by_user_id == creator
    assert stored.created_at == clock.now()
    assert result.usage_count == 0


async def test_register_label_trims_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Label 이름은 앞뒤 공백을 지운 뒤 저장한다.

    테스트 코드: CL-004
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: need에 '  규제 대응  '을 등록한다
    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.NEED, "  규제 대응  ", creator
    )

    # then: 이름은 '규제 대응'이다
    assert result.label.name == "규제 대응"


@pytest.mark.parametrize("name", ["ceo 보고 완료", "CEO 보고 완료", " CEO 보고 완료 "])
async def test_register_label_with_a_duplicate_name_in_the_category_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """같은 구분에 대소문자·공백만 다른 Label 이름은 중복으로 거절하고 저장하지 않는다.

    테스트 코드: CL-006
    """
    # given: authority에 'CEO 보고 완료'가 이미 있다
    creator = await _creator(seeded)
    before = await _names(seeded, BantCategory.AUTHORITY)

    with pytest.raises(DuplicateLabelNameError):
        # when: 대소문자·공백만 다른 이름으로 등록한다
        await RegisterBantLabel(uow_factory, clock).execute(BantCategory.AUTHORITY, name, creator)

    # then: 중복 오류이고 authority 목록은 그대로다
    assert await _names(seeded, BantCategory.AUTHORITY) == before


async def test_register_label_allows_the_same_name_in_another_category(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """다른 구분에 있는 이름으로는 Label을 만들 수 있다.

    테스트 코드: CL-007
    """
    # given: '모름'은 authority·need에만 있다
    creator = await _creator(seeded)

    # when: budget에 '모름'을 등록한다
    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.BUDGET,
        "모름",
        creator,  # authority·need에는 있지만 budget에는 없다
    )

    # then: 등록된다
    assert result.label.name == "모름"


REQUIRED = "Label 이름을 입력하세요."
TOO_LONG = "Label 이름은 50자 이내로 입력하세요."
NUL_MESSAGE = "Label 이름에는 NUL 문자를 쓸 수 없습니다"


@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "blank"])
async def test_register_label_with_a_blank_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """비었거나 공백뿐인 Label 이름은 필수 문구로 거절하고 저장하지 않는다.

    테스트 코드: CL-008
    """
    # given: 기본 Label 23개
    creator = await _creator(seeded)
    before = len(await seeded.bant_labels.list())

    with raises_with(InvalidValueError, REQUIRED):
        # when: need에 빈 이름이나 공백만 있는 이름을 등록한다
        await RegisterBantLabel(uow_factory, clock).execute(BantCategory.NEED, name, creator)

    # then: 'Label 이름을 입력하세요.' 오류이고 Label 수는 그대로다
    assert len(await seeded.bant_labels.list()) == before


async def test_register_label_with_a_51_code_point_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Label 이름이 51자(코드 포인트)면 길이 문구로 거절하고 저장하지 않는다.

    테스트 코드: CL-009
    """
    # given: 기본 Label 23개
    creator = await _creator(seeded)
    before = len(await seeded.bant_labels.list())

    with raises_with(InvalidValueError, TOO_LONG):
        # when: need에 이모지 51개 이름을 등록한다
        await RegisterBantLabel(uow_factory, clock).execute(BantCategory.NEED, "😀" * 51, creator)

    # then: 길이 오류이고 Label 수는 그대로다
    assert len(await seeded.bant_labels.list()) == before


@pytest.mark.parametrize("name", ["a\x00b", "\x00", "name\x00"], ids=["inside", "only", "trailing"])
async def test_register_label_with_a_nul_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """NUL 문자가 든 Label 이름은 등록할 수 없다.

    테스트 코드: CL-010
    """
    # given: 기본 Label 23개
    creator = await _creator(seeded)
    before = len(await seeded.bant_labels.list())

    with raises_with(InvalidValueError, NUL_MESSAGE):
        # when: NUL이 든 이름으로 등록한다
        await RegisterBantLabel(uow_factory, clock).execute(BantCategory.NEED, name, creator)

    # then: NUL 문구 오류이고 Label 수는 그대로다
    assert len(await seeded.bant_labels.list()) == before


async def test_register_label_accepts_a_50_code_point_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Label 이름은 이모지 50개(50 코드 포인트)까지 저장된다.

    테스트 코드: CL-009
    """
    # given: 등록자 사용자가 있다
    creator = await _creator(seeded)

    # when: need에 이모지 50개 이름을 등록한다
    result = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.NEED, "😀" * 50, creator
    )

    # then: 이름이 그대로 저장된다
    assert result.label.name == "😀" * 50


# --- RenameBantLabel ---


async def test_rename_label_changes_the_name_and_keeps_the_rest(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """기본 Label 이름을 바꿔도 기본 표시·자리가 유지되고 수정 시각이 갱신된다.

    테스트 코드: CL-012
    """
    # given: budget의 기본 Label '예산 없음'이 있다
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")
    clock.advance(60)

    # when: '  예산 미확보  '로 이름을 바꾼다
    result = await RenameBantLabel(uow_factory, clock).execute(label.id, "  예산 미확보  ")

    # then: 이름만 바뀌고 기본 표시·default_order는 같으며 updated_at이 서버 시각이다
    stored = await seeded.bant_labels.get(label.id)
    assert result.label.name == stored.name == "예산 미확보"
    assert stored.is_default is True
    assert stored.default_order == label.default_order
    assert stored.updated_at == clock.now()


async def test_rename_label_to_the_same_name_in_another_case_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Label 자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CL-014
    """
    # given: authority에 'CEO 보고 완료'가 있다
    label = await label_by_name(seeded, BantCategory.AUTHORITY, "CEO 보고 완료")

    # when: 'ceo 보고 완료'로 바꾼다
    result = await RenameBantLabel(uow_factory, clock).execute(label.id, "ceo 보고 완료")

    # then: 바뀐 이름이 반환된다
    assert result.label.name == "ceo 보고 완료"


async def test_rename_label_to_another_labels_name_conflicts_and_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """같은 구분의 다른 Label 이름으로 바꾸면 중복으로 거절하고 이름은 그대로다.

    테스트 코드: CL-015
    """
    # given: authority에 'CEO 보고 완료'와 'CISO 보고 완료'가 있다
    label = await label_by_name(seeded, BantCategory.AUTHORITY, "CEO 보고 완료")

    with pytest.raises(DuplicateLabelNameError):
        # when: 'CEO 보고 완료'를 'ciso 보고 완료'로 바꾼다
        await RenameBantLabel(uow_factory, clock).execute(label.id, "ciso 보고 완료")

    # then: 중복 오류이고 이름은 그대로다
    assert (await seeded.bant_labels.get(label.id)).name == "CEO 보고 완료"


async def test_rename_label_to_a_name_that_exists_only_in_another_category_is_allowed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """다른 구분에만 있는 이름으로는 Label 이름을 바꿀 수 있다.

    테스트 코드: CL-016
    """
    # given: '모름'은 authority·need에만 있고 budget에 '미확인'이 있다
    label = await label_by_name(seeded, BantCategory.BUDGET, "미확인")

    # when: budget '미확인'을 '모름'으로 바꾼다
    result = await RenameBantLabel(uow_factory, clock).execute(label.id, "모름")

    # then: 이름이 '모름'으로 바뀐다
    assert result.label.name == "모름"


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", REQUIRED), ("가" * 51, TOO_LONG)],
    ids=["blank", "51-chars"],
)
async def test_rename_label_with_an_invalid_name_keeps_the_name(
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    name: str,
    message: str,
) -> None:
    """공백뿐이거나 51자인 새 이름은 문구에 맞는 오류로 거절하고 이름은 그대로다.

    테스트 코드: CL-017
    """
    # given: budget '예산 없음'이 있다
    label = await label_by_name(seeded, BantCategory.BUDGET, "예산 없음")

    with raises_with(InvalidValueError, message):
        # when: 공백뿐인 이름 또는 51자 이름으로 바꾼다
        await RenameBantLabel(uow_factory, clock).execute(label.id, name)

    # then: 필수·길이 문구 오류이고 이름은 그대로다
    assert (await seeded.bant_labels.get(label.id)).name == "예산 없음"


@pytest.mark.parametrize("name", ["a\x00b", "\x00", "name\x00"], ids=["inside", "only", "trailing"])
async def test_rename_label_with_a_nul_name_keeps_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """NUL 문자가 든 새 Label 이름은 거절하고 이름은 그대로다.

    테스트 코드: CL-010
    """
    # given: budget '단독 예산 확보'가 있다
    label = await label_by_name(seeded, BantCategory.BUDGET, "단독 예산 확보")

    with raises_with(InvalidValueError, NUL_MESSAGE):
        # when: NUL이 든 이름으로 바꾼다
        await RenameBantLabel(uow_factory, clock).execute(label.id, name)

    # then: NUL 문구 오류이고 이름은 그대로다
    assert (await seeded.bant_labels.get(label.id)).name == "단독 예산 확보"


async def test_rename_a_label_made_by_someone_else_keeps_the_creator_and_reports_usage(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """남이 만든 Label의 이름을 바꿔도 만든 사람은 그대로이고 결과에 사용 수가 실린다.

    테스트 코드: CL-013
    """
    # given: KIM이 만든 need '규제 대응'을 Deal 1건이 선택했다
    creator = await _creator(seeded)
    made = await RegisterBantLabel(uow_factory, clock).execute(
        BantCategory.NEED, "규제 대응", creator
    )
    seeded.deals.bant_label_counts = {made.label.id: 1}

    # when: '컴플라이언스 대응'으로 바꾼다
    result = await RenameBantLabel(uow_factory, clock).execute(made.label.id, "컴플라이언스 대응")

    # then: 이름이 바뀌고 사용 수 1이며 직접 만든 항목·만든 사람 그대로다
    stored = await seeded.bant_labels.get(made.label.id)
    assert (result.label.name, result.usage_count) == ("컴플라이언스 대응", 1)
    assert (stored.is_default, stored.created_by_user_id) == (False, creator)


@pytest.mark.parametrize(
    ("name", "message"),
    [("   ", REQUIRED), ("가" * 51, TOO_LONG)],
    ids=["blank", "51-chars"],
)
async def test_rename_a_missing_label_with_an_invalid_name_reports_the_name_first(
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    name: str,
    message: str,
) -> None:
    """없는 id여도 잘못된 이름이면 404가 아니라 이름 오류가 먼저 나온다.

    테스트 코드: CL-017
    """
    # when·then: 공백뿐인 이름 또는 51자 이름으로 바꾼다 → 이름 오류가 먼저다 (전제: 없는 Label id)
    with raises_with(InvalidValueError, message):
        await RenameBantLabel(uow_factory, clock).execute(BantLabelId(new_id()), name)


async def test_rename_missing_label_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """없는 Label의 이름을 바꾸면 찾을 수 없음 오류다.

    테스트 코드: CL-018
    """
    # when·then: 없는 id로 이름을 바꾼다 → Label을 찾을 수 없음 오류다
    with pytest.raises(BantLabelNotFoundError):
        await RenameBantLabel(uow_factory, clock).execute(BantLabelId(new_id()), "아무거나")
