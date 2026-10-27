"""필드 하나의 SQL 식 묶음(`FieldSql`)과 공용 식 도우미.

식은 팩토리로 받아 처음 쓸 때만 만든다(그때 필요한 JOIN이 등록된다).
 - key: 그룹핑·고유 건수·조건 비교에 쓰는 식(id·key·원래 열)
 - value: 결과에 나오는 값(이름 표시). 없으면 key
 - key_value: 포맷이 key일 때의 값. 없으면 key
 - order: 정렬 식. 없으면 value
"""

from functools import cached_property
from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, case, func, literal

from app.domain.report.vocabulary import SortDirection
from app.domain.user.value_objects import RESIGNED_SUFFIX

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from sqlalchemy.sql.selectable import NamedFromClause

    from app.domain.report.fields import FieldOption

type Expr = ColumnElement[Any]
type Factory = Callable[[], Expr]


class FieldSql:
    def __init__(
        self,
        key: Factory,
        *,
        value: Factory | None = None,
        key_value: Factory | None = None,
        order: Factory | None = None,
    ) -> None:
        self._key = key
        self._value = value
        self._key_value = key_value
        self._order = order

    @cached_property
    def key(self) -> Expr:
        return self._key()

    @cached_property
    def value(self) -> Expr:
        return self._value() if self._value else self.key

    @cached_property
    def key_value(self) -> Expr:
        return self._key_value() if self._key_value else self.key

    @cached_property
    def order(self) -> Expr:
        return self._order() if self._order else self.value


def user_name(user: NamedFromClause) -> Expr:
    """사용자 표시 이름. 퇴사자는 이름 뒤에 `(퇴사)`를 붙인다."""
    name = func.coalesce(func.nullif(user.c.display_name, ""), user.c.login_id)
    suffix = case((user.c.deleted_at.is_not(None), literal(RESIGNED_SUFFIX)), else_=literal(""))
    return name + suffix


def static_code(key: Factory, labels: Sequence[tuple[str, str]]) -> FieldSql:
    """정적 선택지 필드: 값은 라벨, 정렬은 선언 순서, key 포맷은 원래 값."""
    names = {k: literal(label) for k, label in labels}
    ranks = {k: literal(index) for index, (k, _) in enumerate(labels)}
    field = FieldSql(
        key,
        value=lambda: case(names, value=field.key),
        order=lambda: case(ranks, value=field.key),
    )
    return field


def option_labels(options: Sequence[FieldOption] | None) -> list[tuple[str, str]]:
    return [(option.value, option.label) for option in options or ()]


def direction_order(expr: Expr, direction: SortDirection) -> Expr:
    """방향대로 정렬하되 NULL은 항상 마지막."""
    ordered = expr.asc() if direction is SortDirection.ASC else expr.desc()
    return ordered.nulls_last()
