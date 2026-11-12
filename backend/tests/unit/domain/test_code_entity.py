"""Code 엔티티 (CD-003, CD-021~023, CD-025~026, CD-037~043)."""

from typing import Any

import pytest

from app.domain.code.entities import Code
from app.domain.code.errors import CodeInUseError, CodeLockedError
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from app.domain.common.errors import InvalidValueError
from tests.factories import NOW, later
from tests.factories_catalog import make_code
from tests.support.ids import new_id

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


def _create(kind: CodeKind = CodeKind.STATUS, **overrides: Any) -> Code:  # noqa: ANN401
    values: dict[str, Any] = {
        "entity_id": CodeId(new_id()),
        "kind": kind,
        "name": "보류",
        "key": CodeKey("code_1"),
        "order": 8,
        "probability_hint": None,
        "now": NOW,
        **overrides,
    }
    return Code.create(**values)


def test_create_uses_the_given_id() -> None:
    """생성할 때 받은 id를 그대로 쓴다."""
    # when: id 21로 만든다
    code = _create(entity_id=CodeId(21))

    # then: id가 21이다
    assert code.id == 21


def test_create_status_code_is_open_without_hint() -> None:
    """새 Status 코드는 결과 open, 힌트 없음이고 등록·변경 시각이 같다."""
    # when: Status 코드를 만든다
    code = _create()

    # then: 값과 시각이 그대로이고 open·힌트 없음이다
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
    """새 Forecast 코드는 결과 open이고 힌트를 그대로 가진다.

    테스트 코드: CD-010
    """
    # when: 힌트가 있는 Forecast 코드를 만든다
    code = _create(
        CodeKind.FORECAST, name="Upside", key=CodeKey("upside"), probability_hint="10-20"
    )

    # then: open이고 힌트가 남는다
    assert code.outcome is ForecastOutcome.OPEN
    assert code.probability_hint == "10-20"


def test_create_status_code_with_hint_is_rejected() -> None:
    """Status에 확률 힌트를 주면 거절한다.

    테스트 코드: CD-023
    """
    # when: 힌트가 있는 Status 코드를 만든다
    with pytest.raises(InvalidValueError) as raised:
        _create(probability_hint="10-20")

    # then: Status 힌트 금지 문구가 난다
    assert str(raised.value) == "Status에는 확률 힌트를 둘 수 없습니다."


@pytest.mark.parametrize(
    ("hint", "expected"),
    [("  10-20  ", "10-20"), ("", None), ("   ", None)],
    ids=["padded", "empty", "blank"],
)
def test_create_normalizes_the_hint(hint: str, expected: str | None) -> None:
    """확률 힌트는 앞뒤 공백을 지우고 비면 없음이다.

    테스트 코드: CD-021
    """
    # when: 공백이 있거나 빈 힌트로 Forecast 코드를 만든다
    code = _create(CodeKind.FORECAST, probability_hint=hint)

    # then: 지운 값이거나 없음이다
    assert code.probability_hint == expected


def test_create_status_code_with_a_blank_hint_has_none() -> None:
    """Status에 공백뿐인 힌트를 주면 허용되고 힌트는 없다.

    테스트 코드: CD-021
    """
    # when: 공백뿐인 힌트로 Status 코드를 만든다
    code = _create(probability_hint="   ")

    # then: 힌트가 없다
    assert code.probability_hint is None


@pytest.mark.parametrize("hint", ["1\x002", "\x00", "10-20\x00"])
def test_create_rejects_a_hint_with_nul(hint: str) -> None:
    """확률 힌트에 NUL이 있으면 거절한다.

    테스트 코드: CD-024
    """
    # when: NUL이 든 힌트로 Forecast 코드를 만든다
    with pytest.raises(InvalidValueError) as raised:
        _create(CodeKind.FORECAST, probability_hint=hint)

    # then: NUL 문구가 난다
    assert str(raised.value) == "확률 힌트에는 NUL 문자를 쓸 수 없습니다"


def test_status_code_with_won_outcome_is_rejected() -> None:
    """Status 코드의 결과는 open만 가능하다."""
    # when: 결과 won인 Status 코드를 만든다
    with pytest.raises(InvalidValueError):
        make_code(CodeKind.STATUS, outcome=ForecastOutcome.WON)

    # then: 값이 잘못되었다는 오류가 난다(위 with 블록)


def test_forecast_hint_of_20_characters_is_accepted() -> None:
    """확률 힌트 20자는 허용한다.

    테스트 코드: CD-022
    """
    # when: 20자 힌트로 Forecast 코드를 만든다
    code = _create(CodeKind.FORECAST, probability_hint="9" * 20)

    # then: 20자가 그대로다
    assert code.probability_hint == "9" * 20


def test_forecast_hint_of_21_characters_is_rejected() -> None:
    """확률 힌트 21자는 거절한다.

    테스트 코드: CD-022
    """
    # when: 21자 힌트로 Forecast 코드를 만든다
    with pytest.raises(InvalidValueError) as raised:
        _create(CodeKind.FORECAST, probability_hint="9" * 21)

    # then: 20자 이내 문구가 난다
    assert str(raised.value) == "확률 힌트는 20자 이내로 입력하세요."


def test_rename_changes_only_the_name_and_touches_updated_at() -> None:
    """이름 변경은 이름과 변경 시각만 바꾼다.

    테스트 코드: CD-025
    """
    # given: Best 코드
    code = make_code(CodeKind.FORECAST, key="best", name="Best", order=2)

    # when: 이름을 바꾼다
    code.rename("가능성 높음", later(60))

    # then: 이름과 변경 시각만 바뀐다
    assert code.name == "가능성 높음"
    assert code.key == CodeKey("best")
    assert code.order == 2
    assert code.created_at == NOW
    assert code.updated_at == later(60)


def test_rename_is_allowed_for_a_locked_code_and_keeps_it_locked() -> None:
    """잠금 코드도 이름을 바꿀 수 있고 잠금은 그대로다.

    테스트 코드: CD-026
    """
    # given: 잠금 코드 계약완료
    code = make_code(CodeKind.STATUS, key="contract_completed", name="계약완료", order=7)

    # when: 이름을 바꾼다
    code.rename("수주", later(60))

    # then: 이름만 바뀌고 key·잠금은 그대로다
    assert code.name == "수주"
    assert code.key == CodeKey("contract_completed")
    assert code.locked


def test_place_changes_only_the_order_and_touches_updated_at() -> None:
    """순서 변경은 순서와 변경 시각만 바꾼다."""
    # given: 제품소개 코드
    code = make_code(CodeKind.STATUS, key="introduction", name="제품소개", order=2)

    # when: 순서를 5로 바꾼다
    code.place(5, later(60))

    # then: 순서와 변경 시각만 바뀐다
    assert code.order == 5
    assert code.name == "제품소개"
    assert code.updated_at == later(60)


@pytest.mark.parametrize(("kind", "key"), LOCKED)
def test_locked_is_true_for_the_five_system_codes(kind: CodeKind, key: str) -> None:
    """다섯 시스템 코드는 잠금이다.

    테스트 코드: CD-003
    """
    # when: 시스템 코드를 만든다
    code = make_code(kind, key=key)

    # then: 잠금이다
    assert code.locked


@pytest.mark.parametrize(("kind", "key"), NOT_LOCKED)
def test_locked_is_false_for_other_codes(kind: CodeKind, key: str) -> None:
    """그 밖의 코드는 다른 종류의 잠금 key와 같아도 잠금이 아니다.

    테스트 코드: CD-003
    """
    # when: 일반 코드를 만든다
    code = make_code(kind, key=key)

    # then: 잠금이 아니다
    assert not code.locked


@pytest.mark.parametrize(("kind", "key"), LOCKED)
def test_locked_code_cannot_be_deleted_even_when_unused(kind: CodeKind, key: str) -> None:
    """잠금 코드는 쓰이지 않아도 삭제할 수 없다.

    테스트 코드: CD-037
    """
    # given: 잠금 코드
    code = make_code(kind, key=key)

    # when: 삭제 가능한지 확인한다(사용 0)
    with pytest.raises(CodeLockedError) as raised:
        code.ensure_deletable(0)

    # then: 잠금 문구가 난다
    assert str(raised.value) == (
        "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."
    )


def test_locked_code_in_use_reports_locked_first() -> None:
    """잠금 코드를 Deal이 쓰고 있으면 잠금 오류가 먼저다.

    테스트 코드: CD-038
    """
    # given: 잠금 코드 기회발굴
    code = make_code(CodeKind.STATUS, key="prospecting")

    # when: Deal 4건이 쓰는 상태에서 삭제 가능한지 확인한다
    with pytest.raises(CodeLockedError):
        code.ensure_deletable(4)

    # then: 사용 중 오류가 아니라 잠금 오류가 난다(위 with 블록)


def test_code_in_use_cannot_be_deleted_and_message_has_the_count() -> None:
    """Deal이 쓰는 코드는 삭제할 수 없고 문구에 Deal 수가 들어간다.

    테스트 코드: CD-040
    """
    # given: 일반 코드 제품소개
    code = make_code(CodeKind.STATUS, key="introduction")

    # when: Deal 3건이 쓰는 상태에서 삭제 가능한지 확인한다
    with pytest.raises(CodeInUseError) as raised:
        code.ensure_deletable(3)

    # then: Deal 3건 문구가 난다
    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 3건)"


def test_unused_unlocked_code_is_deletable() -> None:
    """쓰이지 않는 일반 코드는 삭제할 수 있다.

    테스트 코드: CD-039
    """
    # given: 일반 코드 제품소개
    code = make_code(CodeKind.STATUS, key="introduction")

    # when: 사용 0으로 삭제 가능한지 확인한다
    code.ensure_deletable(0)

    # then: 오류 없이 끝난다
