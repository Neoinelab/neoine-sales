"""head 스키마(P1 Deal 모델 + Vendor·Solution FK)에 원시 SQL로 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. 과거 리비전 스키마용 도우미는
tests.support.legacy_rows에 있다(문자열 컬럼 시절).
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_USER = (
    "insert into users (id, login_id, role, display_name, created_by_user_id, created_at,"
    " updated_at, deleted_at, delete_reason) values (:id, :login_id, :role, :display_name,"
    " :created_by_user_id, now(), now(), :deleted_at, :delete_reason)"
)
INSERT_CONTACT = (
    "insert into contacts (id, kind, company, name, title, email, phone, created_at, updated_at)"
    " values (:id, :kind, :company, :name, :title, :email, :phone, now(), now())"
)
_COLUMNS = (
    "deal_code, name, owner_user_id, users, status_kind,"
    " status_key, forecast_kind, forecast_key, revenue_amount, revenue_date, customer_id,"
    " quote_submitted, quote_submitted_date, poc_state, poc_completed_date, procurement,"
    " created_at, updated_at"
)
_VALUES = (
    ":code, 'n', :owner_user_id, :users, 'status',"
    " :status_key, 'forecast', :forecast_key, :amount, current_date, :customer_id,"
    " :quote_submitted, null, :poc_state, null, '', now(), now()"
)
HAS_COLUMN = (
    "select count(*) from information_schema.columns"
    " where table_schema = 'public' and table_name = 'deals' and column_name = :name"
)


def deal_insert_sql(*, status_entry: bool, text_vendor: bool) -> str:
    """deals INSERT 문. 스키마 시기에 따라 컬럼이 달라진다.

    status_entry: P3(M-P3) 이후라 deals.status_changed_at이 NOT NULL이다.
    text_vendor: Vendor·Solution 관리 리비전 이전이라 deals.vendor/solution 문자열 컬럼이 있다.
    """
    columns, values = _COLUMNS, _VALUES
    if text_vendor:
        columns, values = f"{columns}, vendor, solution", f"{values}, 'v', 's'"
    if status_entry:
        columns, values = f"{columns}, status_changed_at", f"{values}, now()"
    return f"insert into deals ({columns}) values ({values})"  # noqa: S608 - 상수만 조합


INSERT_PARTNER_LINK = (
    "insert into deal_partners (id, deal_code, contact_id, linked_at, unlinked_at)"
    " values (:id, :deal_code, :contact_id, :linked_at, :unlinked_at)"
)
INSERT_BANT = (
    "insert into deal_bant_labels (deal_code, category, label_id)"
    " values (:deal_code, :category, :label_id)"
)
INSERT_HISTORY = (
    "insert into deal_history (deal_code, changed_at, changed_by_user_id, category, target,"
    " before_text, after_text) values (:deal_code, now(), :changed_by_user_id, :category,"
    " 'Deal 등록', '', 'Deal 등록')"
)
# P2: 등록 시점 Status/Forecast 스냅숏(status_kind·forecast_kind는 기본값)이 필수다.
# 유형은 시드된 기본 유형을 이름으로 고른다(`type_name`, 기본 미팅).
INSERT_ACTION = (
    "insert into deal_actions (id, deal_code, action_type_id, action, memo, next_action,"
    " due_date, acted_at, actor_user_id, status_key, forecast_key, created_at, updated_at)"
    " values (:id, :deal_code, (select id from action_types where name = :type_name), 'a', '',"
    " 'n', current_date, now(), :actor_user_id, :status_key, :forecast_key, now(), now())"
)


async def _count(session: AsyncSession, column: str) -> object:
    return (await session.execute(text(HAS_COLUMN), {"name": column})).scalar()


async def insert_user(session: AsyncSession, login_id: str = "kim", **overrides: object) -> UUID:
    """재직 사용자 한 행(스스로 등록한 행). 퇴사 행은 deleted_at/delete_reason을 덮어쓴다."""
    new_id = uuid4()
    values: dict[str, object] = {
        "id": new_id,
        "login_id": login_id,
        "role": "sales",
        "display_name": None,
        "created_by_user_id": new_id,
        "deleted_at": None,
        "delete_reason": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_USER), values)
    return UUID(str(values["id"]))


async def insert_contact(session: AsyncSession, **overrides: object) -> str:
    """연락처 한 행(원시 SQL, 도메인 검사 없음). 제약 검증용이다. 새 id 문자열을 돌려준다."""
    values: dict[str, object] = {
        "id": uuid4(),
        "kind": "customer",
        "company": "회사",
        "name": "담당",
        "title": None,
        "email": None,
        "phone": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_CONTACT), values)
    return str(values["id"])


async def insert_deal(
    session: AsyncSession, customer_id: str, owner_user_id: UUID | None = None, **overrides: object
) -> str:
    """담당자 행이 없으면 새로 만든다. 새 Deal의 code를 돌려준다.

    overrides: code, amount, users, status_key, forecast_key, quote_submitted, poc_state.
    """
    owner = owner_user_id or await insert_user(session, f"o{uuid4().hex[:10]}")
    values: dict[str, object] = {
        "code": "20261016-A001",
        "customer_id": customer_id,
        "amount": 100,
        "owner_user_id": owner,
        "users": None,
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "quote_submitted": None,
        "poc_state": None,
    }
    values.update(overrides)
    # 과거 리비전 스키마에서도 쓰므로 있는 컬럼에 맞춰 INSERT 문을 고른다
    has_entry = (await _count(session, "status_changed_at")) == 1
    has_text_vendor = (await _count(session, "vendor")) == 1
    sql = deal_insert_sql(status_entry=has_entry, text_vendor=has_text_vendor)
    await session.execute(text(sql), values)
    return str(values["code"])


async def insert_partner_link(
    session: AsyncSession, deal_code: str, contact_id: str, **overrides: object
) -> None:
    """파트너 링크 한 행. 기본은 활성(unlinked_at NULL)."""
    values: dict[str, object] = {
        "id": uuid4(),
        "deal_code": deal_code,
        "contact_id": contact_id,
        "linked_at": datetime(2026, 10, 16, 9, 0, tzinfo=UTC),
        "unlinked_at": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_PARTNER_LINK), values)


async def insert_bant(
    session: AsyncSession, deal_code: str, category: str, label_id: object
) -> None:
    """Deal의 BANT 선택 한 행(deal_bant_labels)."""
    params = {"deal_code": deal_code, "category": category, "label_id": label_id}
    await session.execute(text(INSERT_BANT), params)


async def insert_history(
    session: AsyncSession, deal_code: str, changed_by_user_id: UUID, **overrides: object
) -> None:
    """Deal 이력 한 행(deal_history). 기본은 등록 항목이고 category를 덮어쓸 수 있다."""
    values: dict[str, object] = {
        "deal_code": deal_code,
        "changed_by_user_id": changed_by_user_id,
        "category": "created",
    }
    values.update(overrides)
    await session.execute(text(INSERT_HISTORY), values)


async def insert_action(
    session: AsyncSession,
    deal_code: str,
    actor_user_id: UUID,
    *,
    status_key: str = "prospecting",
    forecast_key: str = "pipeline",
    **overrides: object,
) -> UUID:
    """Deal 활동 한 행(deal_actions). 스냅숏 key 기본은 prospecting/pipeline. 새 활동 id를 돌려준다.

    overrides는 INSERT 파라미터를 덮어쓴다(예: id, type_name). 제약 검증용이라
    도메인 검사를 거치지 않는다.
    """
    params: dict[str, object] = {
        "id": uuid4(),
        "deal_code": deal_code,
        "actor_user_id": actor_user_id,
        "status_key": status_key,
        "forecast_key": forecast_key,
        "type_name": "미팅",
        **overrides,
    }
    await session.execute(text(INSERT_ACTION), params)
    return UUID(str(params["id"]))
