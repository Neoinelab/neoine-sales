"""리포트 SQL의 JOIN 등록기. 컬럼·정렬·조건이 이름·코드 표시를 쓸 때만 LEFT JOIN을 한 번씩 추가한다.

모든 JOIN은 행을 늘리지 않는다(대상이 기본 키로 1건이거나, 활성 링크·BANT 구분처럼 최대 1건).
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_

from app.infra.db.models import DealActionRow
from app.infra.db.models_auth import UserRow
from app.infra.db.models_catalog import ActionTypeRow, BantLabelRow, CodeRow, VendorRow
from app.infra.db.models_contact import ContactRow
from app.infra.db.models_deal import DealBantLabelRow, DealPartnerRow, DealRow

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import ColumnElement, FromClause
    from sqlalchemy.sql.selectable import NamedFromClause

    from app.infra.db.base import Base

DEALS = DealRow.__table__
ACTIONS = DealActionRow.__table__


class Joins:
    """사용한 별칭 테이블과 ON 조건. 이름이 같으면 처음 등록한 별칭을 다시 돌려준다."""

    def __init__(self) -> None:
        self._aliases: dict[str, NamedFromClause] = {}
        self._entries: list[tuple[NamedFromClause, ColumnElement[bool]]] = []

    def use(
        self, name: str, model: type[Base], on: Callable[[NamedFromClause], ColumnElement[bool]]
    ) -> NamedFromClause:
        found = self._aliases.get(name)
        if found is not None:
            return found
        alias = model.__table__.alias(name)
        self._aliases[name] = alias
        self._entries.append((alias, on(alias)))
        return alias

    def source(self, *, with_actions: bool) -> FromClause:
        """deals에서 시작해 (행 범위가 Action이면 Action을 안쪽 조인하고) 등록된 별칭을 붙인다."""
        source: FromClause = DEALS
        if with_actions:
            source = source.join(ACTIONS, ACTIONS.c.deal_id == DEALS.c.id)
        for alias, on in self._entries:
            source = source.join(alias, on, isouter=True)
        return source


def _code(
    joins: Joins, name: str, kind: ColumnElement[Any], key: ColumnElement[Any]
) -> NamedFromClause:
    return joins.use(name, CodeRow, lambda a: and_(a.c.kind == kind, a.c.key == key))


def deal_owner(joins: Joins) -> NamedFromClause:
    return joins.use("u_owner", UserRow, lambda a: a.c.id == DEALS.c.owner_user_id)


def deal_vendor(joins: Joins) -> NamedFromClause:
    return joins.use("v", VendorRow, lambda a: a.c.id == DEALS.c.vendor_id)


def deal_customer(joins: Joins) -> NamedFromClause:
    return joins.use("cust", ContactRow, lambda a: a.c.id == DEALS.c.customer_id)


def deal_partner(joins: Joins) -> NamedFromClause:
    """활성 파트너 링크의 연락처(부분 유니크 인덱스로 Deal당 최대 1건)."""
    link = joins.use(
        "dp",
        DealPartnerRow,
        lambda a: and_(a.c.deal_id == DEALS.c.id, a.c.unlinked_at.is_(None)),
    )
    return joins.use("pc", ContactRow, lambda a: a.c.id == link.c.contact_id)


def deal_status_code(joins: Joins) -> NamedFromClause:
    return _code(joins, "cs", DEALS.c.status_kind, DEALS.c.status_key)


def deal_forecast_code(joins: Joins) -> NamedFromClause:
    return _code(joins, "cf", DEALS.c.forecast_kind, DEALS.c.forecast_key)


def deal_bant(joins: Joins, category: str) -> tuple[NamedFromClause, NamedFromClause]:
    """BANT 구분의 (선택 링크, Label). 링크의 label_id가 조건·그룹 키, Label 이름이 표시 값."""
    link = joins.use(
        f"dbl_{category}",
        DealBantLabelRow,
        lambda a: and_(a.c.deal_id == DEALS.c.id, a.c.category == category),
    )
    label = joins.use(f"bl_{category}", BantLabelRow, lambda a: a.c.id == link.c.label_id)
    return link, label


def action_actor(joins: Joins) -> NamedFromClause:
    return joins.use("u_actor", UserRow, lambda a: a.c.id == ACTIONS.c.actor_user_id)


def action_type(joins: Joins) -> NamedFromClause:
    return joins.use("at", ActionTypeRow, lambda a: a.c.id == ACTIONS.c.action_type_id)


def action_status_code(joins: Joins) -> NamedFromClause:
    return _code(joins, "acs", ACTIONS.c.status_kind, ACTIONS.c.status_key)


def action_forecast_code(joins: Joins) -> NamedFromClause:
    return _code(joins, "acf", ACTIONS.c.forecast_kind, ACTIONS.c.forecast_key)
