"""코드 등록·이름 변경 유스케이스 (CD-009~030).

쓰기 유스케이스는 같은 종류의 행을 잠그고(`list(for_update=True)`) 중복·key·order를 정한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.code.register_code import RegisterCode
from app.application.code.rename_code import RenameCode
from app.domain.code.errors import CodeNotFoundError, DuplicateCodeNameError
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.common.errors import InvalidValueError
from tests.support.catalog import add_deals_with_status, code_by_key
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

DUPLICATE = "같은 이름의 코드가 이미 있습니다."
BLANK = "이름을 입력하세요."
TOO_LONG = "이름은 50자 이내로 입력하세요."
NAME_NUL = "이름에는 NUL 문자를 쓸 수 없습니다"
HINT_NUL = "확률 힌트에는 NUL 문자를 쓸 수 없습니다"
HINT_ON_STATUS = "Status에는 확률 힌트를 둘 수 없습니다."
HINT_TOO_LONG = "확률 힌트는 20자 이내로 입력하세요."


async def _count(uow: FakeUnitOfWork, kind: CodeKind) -> int:
    return len(await uow.codes.list(kind))


# --- RegisterCode ---


async def test_register_status_code_appends_with_next_order_and_generated_key(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Status를 추가하면 key가 만들어지고 맨 끝에 open·힌트 없음·사용 0으로 놓인다.

    테스트 코드: CD-009
    """
    # when: Status "Final Review"를 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Final Review", probability_hint=None
    )

    # then: key final_review, order 8, open, 힌트 없음, 사용 0, 시각은 서버 시각, 목록 맨 끝
    assert result.usage_count == 0
    assert result.code.key == CodeKey("final_review")
    assert result.code.order == 8
    assert result.code.outcome is ForecastOutcome.OPEN
    assert result.code.probability_hint is None
    assert not result.code.locked
    assert result.code.created_at == result.code.updated_at == clock.now()
    stored = await seeded.codes.get(result.code.id)
    assert (stored.name, stored.kind, stored.order) == ("Final Review", CodeKind.STATUS, 8)
    assert (await seeded.codes.list(CodeKind.STATUS))[-1].id == result.code.id


async def test_register_forecast_code_keeps_the_probability_hint(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Forecast를 확률 힌트와 함께 추가하면 open으로 맨 끝에 놓이고 힌트가 저장된다.

    테스트 코드: CD-010
    """
    # when: Forecast "Upside"를 힌트 "10-20"과 함께 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Upside", probability_hint="10-20"
    )

    # then: key upside, order 7, open, 힌트가 저장된다
    assert result.code.key == CodeKey("upside")
    assert result.code.order == 7
    assert result.code.outcome is ForecastOutcome.OPEN
    assert (await seeded.codes.get(result.code.id)).probability_hint == "10-20"


async def test_register_forecast_code_without_a_hint_has_none(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """힌트를 주지 않고 Forecast를 추가하면 확률 힌트는 없다.

    테스트 코드: CD-010
    """
    # when: 힌트 없이 Forecast "Upside"를 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Upside", probability_hint=None
    )

    # then: 확률 힌트가 없다
    assert (await seeded.codes.get(result.code.id)).probability_hint is None


async def test_register_code_trims_the_name(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름의 앞뒤 공백은 지워서 저장한다.

    테스트 코드: CD-011
    """
    # when: 앞뒤 공백이 있는 이름으로 Status를 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="  Final Review  ", probability_hint=None
    )

    # then: 이름은 공백이 지워지고 key는 final_review다
    assert result.code.name == "Final Review"
    assert result.code.key == CodeKey("final_review")


@pytest.mark.parametrize("name", ["가" * 50, f" {'가' * 50} "], ids=["50-chars", "50-chars-padded"])
async def test_register_code_accepts_a_name_of_50_characters(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """이름 50자(공백을 지운 뒤 기준)는 허용된다.

    테스트 코드: CD-012
    """
    # when: 50자 이름으로 Status를 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name=name, probability_hint=None
    )

    # then: 저장된 이름은 50자이고 Status가 하나 늘었다
    assert result.code.name == "가" * 50
    assert await _count(seeded, CodeKind.STATUS) == 8


async def test_register_code_rejects_a_name_of_51_characters_and_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름 51자는 거절하고 저장하지 않는다.

    테스트 코드: CD-012
    """
    # when: 51자 이름으로 등록한다 (전제: Status 7개)
    with raises_with(InvalidValueError, TOO_LONG):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name="가" * 51, probability_hint=None
        )

    # then: Status는 7개 그대로다
    assert await _count(seeded, CodeKind.STATUS) == 7


@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "blank"])
async def test_register_code_with_a_blank_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """빈 이름·공백뿐인 이름은 "이름을 입력하세요."로 거절하고 저장하지 않는다.

    테스트 코드: CD-013
    """
    # when: 빈 이름으로 등록한다 (전제: Status 7개)
    with raises_with(InvalidValueError, BLANK):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name=name, probability_hint=None
        )

    # then: Status는 7개 그대로다
    assert await _count(seeded, CodeKind.STATUS) == 7


@pytest.mark.parametrize("name", ["a\x00b", "\x00", "name\x00"])
async def test_register_code_with_a_nul_name_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """이름에 NUL이 있으면 거절하고 코드가 늘지 않는다.

    테스트 코드: CD-014
    """
    # when: NUL이 든 이름으로 등록한다 (전제: Status 7개)
    with raises_with(InvalidValueError, NAME_NUL):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name=name, probability_hint=None
        )

    # then: Status는 7개 그대로다
    assert await _count(seeded, CodeKind.STATUS) == 7


@pytest.mark.parametrize("name", ["best", "BEST", " Best "])
async def test_register_code_with_a_duplicate_name_conflicts_and_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, name: str
) -> None:
    """같은 종류에 대소문자·앞뒤 공백만 다른 이름을 추가하면 충돌이고 저장하지 않는다.

    테스트 코드: CD-015
    """
    # when: Best와 대소문자·공백만 다른 이름으로 Forecast를 등록한다
    #   (전제: Forecast에 기본 코드 Best가 있다)
    with raises_with(DuplicateCodeNameError, DUPLICATE):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.FORECAST, name=name, probability_hint=None
        )

    # then: Forecast는 6개 그대로다
    assert await _count(seeded, CodeKind.FORECAST) == 6


async def test_register_code_with_a_default_status_name_conflicts(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """기본 코드의 이름("기회발굴")도 중복으로 거절한다.

    테스트 코드: CD-015
    """
    # when: 같은 이름으로 Status를 등록한다 (전제: Status에 기본 코드 "기회발굴"이 있다)
    with raises_with(DuplicateCodeNameError, DUPLICATE):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name="기회발굴", probability_hint=None
        )

    # then: Status는 7개 그대로다
    assert await _count(seeded, CodeKind.STATUS) == 7


async def test_register_code_reports_a_duplicate_before_a_status_hint_error(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름이 중복이면서 Status에 힌트를 준 요청은 중복(409) 판정이 먼저다.

    테스트 코드: CD-015
    """
    # when: 중복 이름에 힌트까지 주고 Status를 등록한다 (전제: Status에 기본 코드 "기회발굴"이 있다)
    with raises_with(DuplicateCodeNameError, DUPLICATE):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name="기회발굴", probability_hint="10-20"
        )

    # then: Status는 7개 그대로다
    assert await _count(seeded, CodeKind.STATUS) == 7


async def test_register_code_allows_the_same_name_in_the_other_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """다른 종류의 코드와 같은 이름은 추가할 수 있다.

    테스트 코드: CD-016
    """
    # when: Status "Best"를 등록한다 (전제: Forecast에 "Best"가 있다)
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Best", probability_hint=None
    )

    # then: 등록되고 key는 best다
    assert result.code.name == "Best"
    assert result.code.key == CodeKey("best")


async def test_register_code_without_ascii_name_gets_sequential_keys(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """영문이 없는 이름의 key는 쓰지 않은 code_N 순번이다.

    테스트 코드: CD-017
    """
    # given: 기본 코드(seeded)
    register = RegisterCode(uow_factory, clock)

    # when: 영문이 없는 이름 두 개를 차례로 등록한다
    first = await register.execute(kind=CodeKind.STATUS, name="보류", probability_hint=None)
    second = await register.execute(kind=CodeKind.STATUS, name="검토 중", probability_hint=None)

    # then: key는 code_1, code_2이고 order는 8, 9다
    assert (first.code.key, second.code.key) == (CodeKey("code_1"), CodeKey("code_2"))
    assert (first.code.order, second.code.order) == (8, 9)


async def test_register_code_resolves_key_collision_within_the_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """key가 같은 종류에서 겹치면 번호가 붙는다.

    테스트 코드: CD-018
    """
    # when: Forecast "Best!"를 등록한다 (전제: Forecast에 key best(이름 Best)가 있다)
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Best!", probability_hint=None
    )

    # then: key는 best_2다
    assert result.code.key == CodeKey("best_2")


async def test_register_code_key_only_collides_within_the_same_kind(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """다른 종류의 key와는 겹쳐도 된다(Forecast의 `won`이 있어도 Status의 `won`).

    테스트 코드: CD-018
    """
    # when: Status "Won"을 등록한다 (전제: Forecast에 key won이 있다)
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Won", probability_hint=None
    )

    # then: key는 won이다
    assert result.code.key == CodeKey("won")


async def test_register_code_uses_max_order_plus_one_even_with_gaps(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """중간 순서가 비어 있어도 새 코드는 가장 큰 순서 + 1에 놓인다.

    테스트 코드: CD-020
    """
    # given: Status 제품소개(order 2)를 지워 두었다
    middle = await code_by_key(seeded, CodeKind.STATUS, "introduction")
    await seeded.codes.delete(middle.id)

    # when: Status "Final Review"를 등록한다
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Final Review", probability_hint=None
    )

    # then: order는 8이다
    assert result.code.order == 8


@pytest.mark.parametrize(
    ("hint", "expected"),
    [("  10-20  ", "10-20"), ("", None), ("   ", None)],
    ids=["padded", "empty", "blank"],
)
async def test_register_forecast_code_normalizes_the_hint(
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    hint: str,
    expected: str | None,
) -> None:
    """Forecast 확률 힌트는 앞뒤 공백이 지워지고 빈 값이면 없음으로 저장된다.

    테스트 코드: CD-021
    """
    # when: 공백이 있거나 빈 힌트로 Forecast를 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Upside", probability_hint=hint
    )

    # then: 저장된 힌트는 공백이 지워진 값이거나 없음이다
    assert (await seeded.codes.get(result.code.id)).probability_hint == expected


@pytest.mark.parametrize("hint", ["", "   "], ids=["empty", "blank"])
async def test_register_status_code_with_a_blank_hint_is_allowed_without_a_hint(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, hint: str
) -> None:
    """Status에 빈 힌트를 주면 허용되고 힌트는 없다.

    테스트 코드: CD-021
    """
    # when: 빈 힌트로 Status를 등록한다 (전제: 기본 코드(seeded))
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.STATUS, name="Final Review", probability_hint=hint
    )

    # then: 등록되고 힌트는 없다
    assert (await seeded.codes.get(result.code.id)).probability_hint is None


async def test_register_forecast_code_accepts_a_hint_of_20_characters(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """확률 힌트 20자는 허용된다.

    테스트 코드: CD-022
    """
    # when: 20자 힌트로 Forecast를 등록한다 (전제: Forecast 6개)
    result = await RegisterCode(uow_factory, clock).execute(
        kind=CodeKind.FORECAST, name="Upside", probability_hint="9" * 20
    )

    # then: 힌트가 20자로 저장된다
    assert (await seeded.codes.get(result.code.id)).probability_hint == "9" * 20


async def test_register_forecast_code_rejects_a_hint_of_21_characters_and_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """확률 힌트 21자는 거절하고 저장하지 않는다.

    테스트 코드: CD-022
    """
    # when: 21자 힌트로 Forecast를 등록한다 (전제: Forecast 6개)
    with raises_with(InvalidValueError, HINT_TOO_LONG):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.FORECAST, name="Upside", probability_hint="9" * 21
        )

    # then: Forecast는 6개 그대로다
    assert await _count(seeded, CodeKind.FORECAST) == 6


async def test_register_status_code_with_a_hint_is_rejected_and_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Status에 확률 힌트를 주면 거절하고 저장하지 않는다.

    테스트 코드: CD-023
    """
    # when: 힌트를 주고 Status를 등록한다 (전제: Status 7개)
    with raises_with(InvalidValueError, HINT_ON_STATUS):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.STATUS, name="Final Review", probability_hint="10-20"
        )

    # then: Status는 7개 그대로다
    assert await _count(seeded, CodeKind.STATUS) == 7


@pytest.mark.parametrize("hint", ["1\x002", "\x00", "10-20\x00"])
async def test_register_forecast_code_with_a_nul_hint_stores_nothing(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, hint: str
) -> None:
    """확률 힌트에 NUL이 있으면 거절하고 코드가 늘지 않는다.

    테스트 코드: CD-024
    """
    # when: NUL이 든 힌트로 Forecast를 등록한다 (전제: Forecast 6개)
    with raises_with(InvalidValueError, HINT_NUL):
        await RegisterCode(uow_factory, clock).execute(
            kind=CodeKind.FORECAST, name="Upside", probability_hint=hint
        )

    # then: Forecast는 6개 그대로다
    assert await _count(seeded, CodeKind.FORECAST) == 6


# --- RenameCode ---


async def test_rename_code_changes_only_the_name_and_reports_the_usage_count(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """이름을 바꾸면 이름만 바뀌고 key·순서는 그대로이며 사용 수가 함께 돌아온다.

    테스트 코드: CD-025
    """
    # given: 제품소개를 쓰는 Deal 2건, 시계는 60초 뒤
    await add_deals_with_status(seeded, "introduction", 2)
    introduction = await code_by_key(seeded, CodeKind.STATUS, "introduction")
    clock.advance(60)

    # when: 제품소개를 "  소개  "로 바꾼다
    result = await RenameCode(uow_factory, clock).execute(introduction.id, "  소개  ")

    # then: 이름 "소개", key·order 그대로, 사용 수 2, 변경 시각은 서버 시각이다
    stored = await seeded.codes.get(introduction.id)
    assert result.code.name == stored.name == "소개"
    assert stored.key == CodeKey("introduction")
    assert (stored.order, stored.locked) == (2, False)
    assert result.usage_count == 2
    assert stored.updated_at == clock.now()
    assert "소개" in [c.name for c in await seeded.codes.list(CodeKind.STATUS)]


@pytest.mark.parametrize(
    ("kind", "key", "new_name", "outcome"),
    [
        (CodeKind.STATUS, "contract_completed", "수주 완료", ForecastOutcome.OPEN),
        (CodeKind.FORECAST, "won", "수주", ForecastOutcome.WON),
    ],
)
async def test_rename_locked_code_is_allowed_and_it_stays_locked(  # noqa: PLR0913, PLR0917
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    kind: CodeKind,
    key: str,
    new_name: str,
    outcome: ForecastOutcome,
) -> None:
    """잠금 코드도 이름을 바꿀 수 있고 key·잠금·결과는 그대로다.

    테스트 코드: CD-026
    """
    # given: 잠금 코드(Status 계약완료 또는 Forecast Won)
    code = await code_by_key(seeded, kind, key)

    # when: 이름을 바꾼다
    result = await RenameCode(uow_factory, clock).execute(code.id, new_name)

    # then: 이름만 바뀌고 key·잠금·order·결과는 그대로다
    assert result.code.name == new_name
    assert result.code.key == CodeKey(key)
    assert result.code.locked
    assert result.code.order == code.order
    assert result.code.outcome is outcome


@pytest.mark.parametrize(
    ("kind", "key", "new_name"),
    [(CodeKind.STATUS, "poc_completed", "poc완료"), (CodeKind.FORECAST, "best", "BEST")],
)
async def test_rename_code_to_the_same_name_in_another_case_is_allowed(  # noqa: PLR0913, PLR0917
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    kind: CodeKind,
    key: str,
    new_name: str,
) -> None:
    """자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CD-027
    """
    # given: 기본 코드
    code = await code_by_key(seeded, kind, key)

    # when: 자기 이름과 대소문자만 다른 이름으로 바꾼다
    result = await RenameCode(uow_factory, clock).execute(code.id, new_name)

    # then: 새 이름이 저장된다
    assert result.code.name == new_name
    assert (await seeded.codes.get(code.id)).name == new_name


@pytest.mark.parametrize(
    ("kind", "key", "other_name", "old_name"),
    [
        (CodeKind.STATUS, "introduction", "기회발굴", "제품소개"),
        (CodeKind.FORECAST, "best", "commit", "Best"),
    ],
)
async def test_rename_code_to_another_codes_name_conflicts_and_keeps_the_name(  # noqa: PLR0913, PLR0917
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    kind: CodeKind,
    key: str,
    other_name: str,
    old_name: str,
) -> None:
    """같은 종류의 다른 코드 이름으로 바꾸면 충돌이고 이름은 그대로다.

    테스트 코드: CD-028
    """
    # given: 같은 종류에 다른 코드 이름이 있다
    code = await code_by_key(seeded, kind, key)

    # when: 그 이름으로 바꾼다
    with raises_with(DuplicateCodeNameError, DUPLICATE):
        await RenameCode(uow_factory, clock).execute(code.id, other_name)

    # then: 이름은 그대로다
    assert (await seeded.codes.get(code.id)).name == old_name


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("", BLANK),
        ("   ", BLANK),
        ("가" * 51, TOO_LONG),
        ("a\x00b", NAME_NUL),
    ],
    ids=["empty", "blank", "51-chars", "nul"],
)
async def test_rename_code_with_an_invalid_name_keeps_the_name(
    seeded: FakeUnitOfWork,
    uow_factory: UnitOfWorkFactory,
    clock: FixedClock,
    name: str,
    message: str,
) -> None:
    """빈 이름·51자·NUL 이름으로 바꾸면 거절하고 이름은 그대로다.

    테스트 코드: CD-029
    """
    # given: 제품소개
    code = await code_by_key(seeded, CodeKind.STATUS, "introduction")

    # when: 잘못된 이름으로 바꾼다
    with raises_with(InvalidValueError, message):
        await RenameCode(uow_factory, clock).execute(code.id, name)

    # then: 이름은 "제품소개" 그대로다
    assert (await seeded.codes.get(code.id)).name == "제품소개"


async def test_rename_missing_code_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """없는 코드의 이름을 바꾸면 찾을 수 없다.

    테스트 코드: CD-030
    """
    # given: 없는 id
    missing = CodeId(new_id())

    # when: 그 id의 이름을 바꾼다
    with pytest.raises(CodeNotFoundError) as raised:
        await RenameCode(uow_factory, clock).execute(missing, "아무거나")

    # then: 없는 id를 가리키는 오류다
    assert raised.value.identifier == missing
