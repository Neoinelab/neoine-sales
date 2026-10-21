"""코드(Status·Forecast)와 BANT Label 테스트용 생성 도우미. 기본은 유효한 더미 값이다."""

from typing import Any

from app.domain.bant.entities import BantLabel
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from tests.factories import NOW
from tests.support.ids import new_id


def make_code(kind: CodeKind = CodeKind.STATUS, **overrides: Any) -> Code:  # noqa: ANN401
    """저장하지 않은 코드. overrides: key(str), name, order, outcome, probability_hint, now."""
    now = overrides.pop("now", NOW)
    values: dict[str, Any] = {
        "key": "custom",
        "name": "사용자 코드",
        "order": 1,
        "outcome": ForecastOutcome.OPEN,
        "probability_hint": None,
        **overrides,
    }
    return Code(
        id=CodeId(new_id()),
        kind=kind,
        key=CodeKey(values.pop("key")),
        created_at=now,
        updated_at=now,
        **values,
    )


def make_label(category: BantCategory = BantCategory.BUDGET, **overrides: Any) -> BantLabel:  # noqa: ANN401
    """저장하지 않은 Label. overrides: name, is_default, default_order, created_by, now.

    기본 Label이면 is_default=True와 default_order를 함께 준다.
    """
    now = overrides.pop("now", NOW)
    values: dict[str, Any] = {
        "name": "테스트 Label",
        "is_default": False,
        "default_order": None,
        "created_by": None,
        **overrides,
    }
    return BantLabel(
        id=BantLabelId(new_id()),
        category=category,
        name=values["name"],
        is_default=values["is_default"],
        default_order=values["default_order"],
        created_by_user_id=values["created_by"],
        created_at=now,
        updated_at=now,
    )
