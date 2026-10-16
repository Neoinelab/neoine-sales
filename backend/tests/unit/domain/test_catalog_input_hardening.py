"""코드·BANT Label 입력 보강(Major 3, Minor): NUL 거절과 확률 힌트 정규화.

PostgreSQL은 문자열의 NUL을 거부해 500이 나므로, 도메인이 기존 규약
(`domain/common/validation.py`)처럼 InvalidValueError(422)로 먼저 거른다.
확률 힌트는 화면 표시용 문구라 앞뒤 공백을 제거하고 빈 값은 None으로 저장한다.
"""

import pytest

from app.domain.bant.values import LABEL_NAME_MAX, normalize_label_name
from app.domain.code.entities import Code
from app.domain.code.rules import normalize_code_name
from app.domain.code.values import PROBABILITY_HINT_MAX, CodeKey, CodeKind
from app.domain.common.errors import InvalidValueError
from tests.factories import NOW

NUL_NAMES = ["a\x00b", "\x00", "name\x00", "\x00name", " \x00 "]
NUL_IDS = ["inside", "only", "trailing", "leading", "padded"]


def _create(kind: CodeKind, hint: str | None) -> Code:
    return Code.create(
        kind=kind, name="Upside", key=CodeKey("upside"), order=7, probability_hint=hint, now=NOW
    )


# --- NUL (Major 3) ---


@pytest.mark.parametrize("raw", NUL_NAMES, ids=NUL_IDS)
def test_code_name_with_a_nul_is_invalid(raw: str) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        normalize_code_name(raw)


@pytest.mark.parametrize("raw", NUL_NAMES, ids=NUL_IDS)
def test_label_name_with_a_nul_is_invalid(raw: str) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        normalize_label_name(raw)


@pytest.mark.parametrize("raw", ["1\x002", "\x00", "10-20\x00"], ids=["inside", "only", "trailing"])
def test_probability_hint_with_a_nul_is_invalid(raw: str) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        _create(CodeKind.FORECAST, raw)


def test_code_name_without_a_nul_keeps_working_after_the_check() -> None:
    assert normalize_code_name("  Final Review  ") == "Final Review"


def test_label_name_without_a_nul_keeps_working_after_the_check() -> None:
    assert normalize_label_name("  예산 확정  ") == "예산 확정"
    assert len(normalize_label_name("가" * LABEL_NAME_MAX)) == LABEL_NAME_MAX


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
    assert _create(CodeKind.FORECAST, raw).probability_hint == stored


@pytest.mark.parametrize("raw", ["", "   "], ids=["empty", "blank"])
def test_status_with_a_blank_hint_is_allowed_and_has_no_hint(raw: str) -> None:
    code = _create(CodeKind.STATUS, raw)

    assert code.probability_hint is None


def test_status_with_a_real_hint_is_still_invalid() -> None:
    with pytest.raises(InvalidValueError):
        _create(CodeKind.STATUS, "10-20")


def test_hint_length_limit_applies_after_trimming() -> None:
    longest = "9" * PROBABILITY_HINT_MAX

    assert _create(CodeKind.FORECAST, f"  {longest}  ").probability_hint == longest


def test_hint_over_the_limit_after_trimming_is_invalid() -> None:
    with pytest.raises(InvalidValueError):
        _create(CodeKind.FORECAST, "9" * (PROBABILITY_HINT_MAX + 1))
