"""head 스키마(BIGINT id)에 원시 SQL로 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. 대리 키 테이블의 id는 `tests.support.ids.new_id()`가
주는 10억대 번호를 명시해서 넣고(시퀀스와 겹치지 않는다), Deal 소속 행(파트너 링크·BANT·이력·활동·
첨부)은 `deal_code`로 Deal을 찾아 `deal_id`를 채운다. 없는 Deal을 일부러 가리키려면 `deal_id=`를
덮어쓴다. UUID 시절(`e8c2b4f6a1d9` 이하) 스키마용 도우미는 `tests.support.uuid_era`에 있다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text

from tests.support.ids import new_id

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
# deals.id는 DB 기본값(IDENTITY)이 매긴다: 도메인이 모르는 대리 키다.
INSERT_DEAL = (
    "insert into deals (deal_code, name, owner_user_id, users, status_kind, status_key,"
    " forecast_kind, forecast_key, revenue_amount, revenue_date, customer_id, quote_submitted,"
    " quote_submitted_date, poc_state, poc_completed_date, procurement, created_at, updated_at,"
    " status_changed_at) values (:code, 'n', :owner_user_id, :users, 'status', :status_key,"
    " 'forecast', :forecast_key, :amount, current_date, :customer_id, :quote_submitted, null,"
    " :poc_state, null, '', now(), now(), now())"
)
HAS_SOLUTION_TEXT = (
    "select count(*) from information_schema.columns"
    " where table_schema = 'public' and table_name = 'deals' and column_name = 'solution'"
)
DEAL_ID_OF = "select id from deals where deal_code = :deal_code"
INSERT_PARTNER_LINK = (
    "insert into deal_partners (deal_id, contact_id, linked_at, unlinked_at)"
    " values (:deal_id, :contact_id, :linked_at, :unlinked_at)"
)
INSERT_BANT = (
    "insert into deal_bant_labels (deal_id, category, label_id)"
    " values (:deal_id, :category, :label_id)"
)
INSERT_HISTORY = (
    "insert into deal_history (deal_id, changed_at, changed_by_user_id, category, target,"
    " before_text, after_text) values (:deal_id, now(), :changed_by_user_id, :category,"
    " 'Deal 등록', '', 'Deal 등록')"
)
# 등록 시점 Status/Forecast 스냅숏(status_kind·forecast_kind는 기본값)이 필수다.
# 유형은 시드된 기본 유형을 이름으로 고른다(`type_name`, 기본 미팅).
INSERT_ACTION = (
    "insert into deal_actions (id, deal_id, action_type_id, action, memo, next_action,"
    " due_date, acted_at, actor_user_id, status_key, forecast_key, next_action_status,"
    " created_at, updated_at)"
    " values (:id, :deal_id, (select id from action_types where name = :type_name), 'a', '',"
    " 'n', current_date, now(), :actor_user_id, :status_key, :forecast_key, 'open', now(), now())"
)


async def insert_user(session: AsyncSession, login_id: str = "kim", **overrides: object) -> int:
    """재직 사용자 한 행(스스로 등록한 행). 퇴사 행은 deleted_at/delete_reason을 덮어쓴다."""
    new_user_id = new_id()
    values: dict[str, object] = {
        "id": new_user_id,
        "login_id": login_id,
        "role": "sales",
        "display_name": None,
        "created_by_user_id": new_user_id,
        "deleted_at": None,
        "delete_reason": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_USER), values)
    return int(str(values["id"]))


async def insert_contact(session: AsyncSession, **overrides: object) -> int:
    """연락처 한 행(원시 SQL, 도메인 검사 없음). 제약 검증용이다. 새 id를 돌려준다."""
    values: dict[str, object] = {
        "id": new_id(),
        "kind": "customer",
        "company": "회사",
        "name": "담당",
        "title": None,
        "email": None,
        "phone": None,
    }
    values.update(overrides)
    await session.execute(text(INSERT_CONTACT), values)
    return int(str(values["id"]))


async def insert_deal(
    session: AsyncSession, customer_id: int, owner_user_id: int | None = None, **overrides: object
) -> str:
    """담당자 행이 없으면 새로 만든다. 새 Deal의 code를 돌려준다(Deal id는 DB가 매긴다).

    overrides: code, amount, users, status_key, forecast_key, quote_submitted, poc_state, solution.

    `deals.solution`(Solution 자유 텍스트) 컬럼이 있는 스키마(그 리비전 이후)에서는 `solution`
    값(기본 "")을 함께 넣는다. 이전 리비전 스키마에서는 넣지 않는다(마이그레이션 테스트 공용).
    """
    owner = owner_user_id or await insert_user(session, f"o{new_id()}")
    values: dict[str, object] = {
        "code": "20261016-A001",
        "customer_id": customer_id,
        "amount": 100,
        "owner_user_id": owner,
        "users": 10,
        "status_key": "prospecting",
        "forecast_key": "pipeline",
        "quote_submitted": None,
        "poc_state": None,
    }
    values.update(overrides)
    statement = INSERT_DEAL
    if (await session.execute(text(HAS_SOLUTION_TEXT))).scalar_one():
        statement = statement.replace(
            "procurement, created_at", "procurement, solution, created_at"
        )
        statement = statement.replace(
            "'', now(), now(), now())", "'', :solution, now(), now(), now())"
        )
        values.setdefault("solution", "")
    else:
        values.pop("solution", None)
    await session.execute(text(statement), values)
    return str(values["code"])


async def deal_id_of(session: AsyncSession, deal_code: str) -> int | None:
    """deal_code의 Deal 내부 id(없으면 None)."""
    found = (await session.execute(text(DEAL_ID_OF), {"deal_code": deal_code})).scalar()
    return None if found is None else int(found)


async def _with_deal_id(
    session: AsyncSession, deal_code: str, values: dict[str, object]
) -> dict[str, object]:
    """values에 deal_id를 채운다. 호출자가 deal_id를 덮어쓰지 않았으면 deal_code로 찾는다."""
    if "deal_id" not in values:
        values["deal_id"] = await deal_id_of(session, deal_code)
    return values


async def insert_partner_link(
    session: AsyncSession, deal_code: str, contact_id: int, **overrides: object
) -> None:
    """파트너 링크 한 행(id는 DB가 매긴다). 기본은 활성(unlinked_at NULL)."""
    values: dict[str, object] = {
        "contact_id": contact_id,
        "linked_at": datetime(2026, 10, 16, 9, 0, tzinfo=UTC),
        "unlinked_at": None,
        **overrides,
    }
    await session.execute(
        text(INSERT_PARTNER_LINK), await _with_deal_id(session, deal_code, values)
    )


async def insert_bant(
    session: AsyncSession, deal_code: str, category: str, label_id: object, **overrides: object
) -> None:
    """Deal의 BANT 선택 한 행(deal_bant_labels)."""
    values: dict[str, object] = {"category": category, "label_id": label_id, **overrides}
    await session.execute(text(INSERT_BANT), await _with_deal_id(session, deal_code, values))


async def insert_history(
    session: AsyncSession, deal_code: str, changed_by_user_id: int, **overrides: object
) -> None:
    """Deal 이력 한 행(deal_history, id는 DB가 매긴다). 기본은 등록 항목이고 category를 덮어쓴다."""
    values: dict[str, object] = {
        "changed_by_user_id": changed_by_user_id,
        "category": "created",
        **overrides,
    }
    await session.execute(text(INSERT_HISTORY), await _with_deal_id(session, deal_code, values))


async def insert_action(
    session: AsyncSession,
    deal_code: str,
    actor_user_id: int,
    *,
    status_key: str = "prospecting",
    forecast_key: str = "pipeline",
    **overrides: object,
) -> int:
    """Deal 활동 한 행(deal_actions). 스냅숏 key 기본은 prospecting/pipeline. 새 활동 id를 돌려준다.

    overrides는 INSERT 파라미터를 덮어쓴다(예: id, type_name, deal_id). 제약 검증용이라
    도메인 검사를 거치지 않는다.
    """
    params: dict[str, object] = {
        "id": new_id(),
        "actor_user_id": actor_user_id,
        "status_key": status_key,
        "forecast_key": forecast_key,
        "type_name": "미팅",
        **overrides,
    }
    await session.execute(text(INSERT_ACTION), await _with_deal_id(session, deal_code, params))
    return int(str(params["id"]))
