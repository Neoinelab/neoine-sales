"""Code 엔티티 (AC-01·03·05·07·08)."""

import pytest
from app.domain.code.entities import Code
from app.domain.code.errors import CodeInUseError, CodeLockedError
from app.domain.code.values import CodeKey, CodeKind, ForecastOutcome

from app.domain.common.errors import InvalidValueError
from tests.factories import NOW, later
from tests.factories_catalog import make_code

LOCKED = [
    (CodeKind.STATUS, "prospecting"),
    (CodeKind.STATUS, "contract_completed"),
    (CodeKind.FORECAST, "pipeline"),
    (CodeKind.FORECAST, "won"),
    (CodeKind.FORECAST, "lost"),
]
NOT_LOCKED = [
    (CodeKind.STATUS, "introduction"),
    (CodeKind.STATUS, "won"),  # 잠금은 종류별: Forecast의 잠금 key라도 Status에서는 일반 코드
    (CodeKind.FORECAST, "best"),
    (CodeKind.FORECAST, "prospecting"),
]


def test_create_status_code_is_open_without_hint() -> None:
    code = Code.create(
        kind=CodeKind.STATUS,
        name="보류",
        key=CodeKey("code_1"),
        order=8,
        probability_hint=None,
        now=NOW,
    )

    assert (code.kind, code.name, code.key, code.order) == (
        CodeKind.STATUS,
        "보류",
        CodeKey("code_1"),
        8,
    )
    assert code.outcome is ForecastOutcome.OPEN
    assert code.probability_hint is None
    assert code.created_at == code.updated_at == NOW


def test_create_forecast_code_is_open_and_keeps_the_hint() -> None:
    code = Code.create(
        kind=CodeKind.FORECAST,
        name="Upside",
        key=CodeKey("upside"),
        order=7,
        probability_hint="10-20",
        now=NOW,
    )

    assert code.outcome is ForecastOutcome.OPEN
    assert code.probability_hint == "10-20"


def test_create_status_code_with_hint_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        Code.create(
            kind=CodeKind.STATUS,
            name="보류",
            key=CodeKey("code_1"),
            order=8,
            probability_hint="10-20",
            now=NOW,
        )


def test_status_code_with_won_outcome_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        make_code(CodeKind.STATUS, outcome=ForecastOutcome.WON)


def _create_forecast(hint: str) -> Code:
    return Code.create(
        kind=CodeKind.FORECAST,
        name="Upside",
        key=CodeKey("upside"),
        order=7,
        probability_hint=hint,
        now=NOW,
    )


def test_forecast_hint_of_20_characters_is_accepted() -> None:
    assert _create_forecast("9" * 20).probability_hint == "9" * 20


def test_forecast_hint_of_21_characters_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        _create_forecast("9" * 21)


def test_rename_changes_only_the_name_and_touches_updated_at() -> None:
    code = make_code(CodeKind.FORECAST, key="best", name="Best", order=2)

    code.rename("가능성 높음", later(60))

    assert code.name == "가능성 높음"
    assert code.key == CodeKey("best")
    assert code.order == 2
    assert code.created_at == NOW
    assert code.updated_at == later(60)


def test_rename_is_allowed_for_a_locked_code_and_keeps_it_locked() -> None:
    code = make_code(CodeKind.STATUS, key="contract_completed", name="계약완료", order=7)

    code.rename("수주", later(60))

    assert code.name == "수주"
    assert code.key == CodeKey("contract_completed")
    assert code.locked


def test_place_changes_only_the_order_and_touches_updated_at() -> None:
    code = make_code(CodeKind.STATUS, key="introduction", name="제품소개", order=2)

    code.place(5, later(60))

    assert code.order == 5
    assert code.name == "제품소개"
    assert code.updated_at == later(60)


@pytest.mark.parametrize(("kind", "key"), LOCKED)
def test_locked_is_true_for_the_five_system_codes(kind: CodeKind, key: str) -> None:
    assert make_code(kind, key=key).locked


@pytest.mark.parametrize(("kind", "key"), NOT_LOCKED)
def test_locked_is_false_for_other_codes(kind: CodeKind, key: str) -> None:
    assert not make_code(kind, key=key).locked


@pytest.mark.parametrize(("kind", "key"), LOCKED)
def test_locked_code_cannot_be_deleted_even_when_unused(kind: CodeKind, key: str) -> None:
    code = make_code(kind, key=key)

    with pytest.raises(CodeLockedError) as raised:
        code.ensure_deletable(0)

    assert str(raised.value) == (
        "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."
    )


def test_locked_code_in_use_reports_locked_first() -> None:
    code = make_code(CodeKind.STATUS, key="prospecting")

    with pytest.raises(CodeLockedError):
        code.ensure_deletable(4)


def test_code_in_use_cannot_be_deleted_and_message_has_the_count() -> None:
    code = make_code(CodeKind.STATUS, key="introduction")

    with pytest.raises(CodeInUseError) as raised:
        code.ensure_deletable(3)

    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 3건)"


def test_unused_unlocked_code_is_deletable() -> None:
    make_code(CodeKind.STATUS, key="introduction").ensure_deletable(0)
