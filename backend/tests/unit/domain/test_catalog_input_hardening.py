"""코드·BANT Label 입력 보강(Major 3, Minor): NUL 거절과 확률 힌트 정규화.

PostgreSQL은 문자열의 NUL을 거부해 500이 나므로, 도메인이 기존 규약
(`domain/common/validation.py`)처럼 InvalidValueError(422)로 먼저 거른다.
확률 힌트는 화면 표시용 문구라 앞뒤 공백을 제거하고 빈 값은 None으로 저장한다.
"""

import pytest

from app.domain.bant.values import LABEL_NAME_MAX, normalize_label_name
from app.domain.code.entities import Code
from app.domain.code.rules import normalize_code_name
from app.domain.code.values import PROBABILITY_HINT_MAX, CodeId, CodeKey, CodeKind
from app.domain.common.errors import InvalidValueError
from tests.factories import NOW
from tests.support.ids import new_id

NUL_NAMES = ["a\x00b", "\x00", "name\x00", "\x00name", " \x00 "]
NUL_IDS = ["inside", "only", "trailing", "leading", "padded"]


def _create(kind: CodeKind, hint: str | None) -> Code:
    return Code.create(
        entity_id=CodeId(new_id()),
        kind=kind,
        name="Upside",
        key=CodeKey("upside"),
        order=7,
        probability_hint=hint,
        now=NOW,
    )


# --- NUL (Major 3) ---


@pytest.mark.parametrize("raw", NUL_NAMES, ids=NUL_IDS)
def test_code_name_with_a_nul_is_invalid(raw: str) -> None:
    """코드 이름에 NUL이 있으면 InvalidValueError인지 확인한다."""
    # when·then: NUL이 든 이름을 정규화하면 NUL 오류가 난다
    with pytest.raises(InvalidValueError, match="NUL"):
        normalize_code_name(raw)


@pytest.mark.parametrize("raw", NUL_NAMES, ids=NUL_IDS)
def test_label_name_with_a_nul_is_invalid(raw: str) -> None:
    """Label 이름에 NUL이 있으면 InvalidValueError인지 확인한다."""
    # when·then: NUL이 든 이름을 정규화하면 NUL 오류가 난다
    with pytest.raises(InvalidValueError, match="NUL"):
        normalize_label_name(raw)


@pytest.mark.parametrize("raw", ["1\x002", "\x00", "10-20\x00"], ids=["inside", "only", "trailing"])
def test_probability_hint_with_a_nul_is_invalid(raw: str) -> None:
    """확률 힌트에 NUL이 있으면 InvalidValueError인지 확인한다."""
    # when·then: NUL이 든 힌트로 코드를 만들면 NUL 오류가 난다
    with pytest.raises(InvalidValueError, match="NUL"):
        _create(CodeKind.FORECAST, raw)


def test_code_name_without_a_nul_keeps_working_after_the_check() -> None:
    """NUL이 없는 코드 이름은 앞뒤 공백만 정리되는지 확인한다."""
    # when: 공백이 붙은 이름을 정규화한다
    result = normalize_code_name("  Final Review  ")
    # then: 공백이 제거된다
    assert result == "Final Review"


def test_label_name_without_a_nul_keeps_working_after_the_check() -> None:
    """NUL이 없는 Label 이름은 정상 정규화되는지 확인한다."""
    # when: 공백이 붙은 이름과 최대 길이 이름을 정규화한다
    trimmed = normalize_label_name("  예산 확정  ")
    longest = normalize_label_name("가" * LABEL_NAME_MAX)

    # then: 공백이 제거되고 최대 길이 이름은 그대로 유지된다
    assert trimmed == "예산 확정"
    assert len(longest) == LABEL_NAME_MAX


# --- 확률 힌트 정규화 (Minor) ---


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("10-20", "10-20"),
        ("  10-20  ", "10-20"),
        ("\t10-20\n", "10-20"),
        (" 10 - 20 ", "10 - 20"),
        (None, None),
        ("", None),
        ("   ", None),
        ("\t\n", None),
    ],
    ids=["plain", "padded", "tabs", "inner-space-kept", "none", "empty", "blank", "controls"],
)
def test_forecast_hint_is_trimmed_and_blank_becomes_none(
    raw: str | None, stored: str | None
) -> None:
    """Forecast 확률 힌트는 앞뒤 공백이 제거되고 빈 값은 None이 되는지 확인한다."""
    # when: 힌트를 넣어 코드를 만든다
    result = _create(CodeKind.FORECAST, raw).probability_hint
    # then: 저장된 힌트가 정규화된 값이다
    assert result == stored


@pytest.mark.parametrize("raw", ["", "   "], ids=["empty", "blank"])
def test_status_with_a_blank_hint_is_allowed_and_has_no_hint(raw: str) -> None:
    """Status 코드에 빈 힌트를 주면 허용되고 힌트가 없는지 확인한다."""
    # when: 빈 힌트로 Status 코드를 만든다
    code = _create(CodeKind.STATUS, raw)

    # then: 힌트가 None이다
    assert code.probability_hint is None


def test_status_with_a_real_hint_is_still_invalid() -> None:
    """Status 코드에 실제 힌트를 주면 오류인지 확인한다."""
    # when·then: 값이 있는 힌트로 Status 코드를 만들면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        _create(CodeKind.STATUS, "10-20")


def test_hint_length_limit_applies_after_trimming() -> None:
    """길이 제한이 공백 제거 뒤 값에 적용되는지 확인한다."""
    # given: 최대 길이 힌트가 있다
    longest = "9" * PROBABILITY_HINT_MAX

    # when: 앞뒤 공백을 붙인 최대 길이 힌트로 코드를 만든다
    result = _create(CodeKind.FORECAST, f"  {longest}  ").probability_hint
    # then: 힌트가 공백 없이 최대 길이로 저장된다
    assert result == longest


def test_hint_over_the_limit_after_trimming_is_invalid() -> None:
    """공백 제거 뒤에도 최대 길이를 넘는 힌트는 오류인지 확인한다."""
    # when·then: 최대 길이를 넘는 힌트로 만들면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        _create(CodeKind.FORECAST, "9" * (PROBABILITY_HINT_MAX + 1))
