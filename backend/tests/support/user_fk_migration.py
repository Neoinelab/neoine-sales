"""사용자 FK 마이그레이션 테스트 준비 도우미: LEGACY_HEAD 스키마에 원시 SQL로 행을 넣는다.

LEGACY_HEAD 스키마는 사용자 참조가 모두 문자열이다: deals.owner(이름),
deals.owner_user_id(등록자 login id), deal_actions.actor(이름),
deal_stage_changes.changed_by_subject/name, auth_sessions.subject, users.created_by,
directory_settings.updated_by.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.user_ids import uid

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

KIM, PARK, ROOT = uid("kim"), uid("park"), uid("root")

INSERT_USER = (
    "insert into users (id, login_id, role, display_name, created_by, created_at, updated_at)"
    " values (:id, :login_id, :role, :display_name, :created_by, now(), now())"
)
INSERT_CUSTOMER = (
    "insert into customers (id, company_name, contact_name, notes, created_at, updated_at)"
    " values (:id, 'c', 'n', '', now(), now())"
)
INSERT_DEAL = (
    "insert into deals (id, code, name, owner, owner_user_id, vendor, solution, revenue_amount,"
    " revenue_currency, revenue_date, customer_id, created_at, updated_at) values (:id, :code,"
    " 'n', :owner, :registrant, 'v', 's', 100, 'KRW', current_date, :customer_id, now(), now())"
)
INSERT_ACTION = (
    "insert into deal_actions (id, deal_id, action_type, action, memo, next_action, due_date,"
    " acted_at, actor, created_at, updated_at) values (:id, :deal_id, 'meeting', 'a', '', 'n',"
    " current_date, now(), :actor, now(), now())"
)
INSERT_CHANGE = (
    "insert into deal_stage_changes (id, deal_id, from_stage, to_stage, reason,"
    " changed_by_subject, changed_by_name, changed_at) values (:id, :deal_id, 'prospecting',"
    " 'introduction', null, :subject, :name, now())"
)
INSERT_SESSION = (
    "insert into auth_sessions (id, token_hash, subject, email, name, role, created_at,"
    " expires_at) values (:id, :token, :subject, null, 'n', 'sales', now(),"
    " now() + interval '1 hour')"
)
INSERT_SETTINGS = (
    "insert into directory_settings (id, revision, server_urls, use_starttls, bind_template,"
    " base_dn, user_filter, display_name_attribute, email_attribute, connect_timeout_seconds,"
    " receive_timeout_seconds, updated_at, updated_by) values (1, 1,"
    " cast('[\"ldaps://dc1.corp.test\"]' as jsonb), false, 'cn={login_id}', 'dc=corp',"
    " '(cn={login_id})', 'displayName', 'mail', 5, 10, now(), :updated_by)"
)


@dataclass
class LegacyData:
    """직전 head 스키마에 넣을 업무 데이터. 기본값은 모두 변환 가능한 값이다."""

    users: list[tuple[UUID, str, str | None, str, str]] = field(
        default_factory=lambda: [
            (ROOT, "root", "루트", "admin", "root"),
            (KIM, "kim", "김영업", "sales", "root"),
            (PARK, "park", "박영업", "sales", "KIM"),  # created_by는 login id(대소문자 무관)
        ]
    )
    deals: list[tuple[str, str, str | None]] = field(
        default_factory=lambda: [
            ("D-1", "박영업", "KIM"),  # (코드, owner 이름, 등록자 login id)
            ("D-2", " kim ", None),  # owner가 login id(공백·대소문자 다름), 등록자 없음(과거 딜)
        ]
    )
    actions: list[tuple[str, str]] = field(default_factory=lambda: [("D-1", "박영업")])
    changes: list[tuple[str, str, str]] = field(
        default_factory=lambda: [("D-1", "Park", "박영업")]  # (코드, subject, name)
    )
    sessions: list[str] = field(default_factory=lambda: ["kim", "PARK"])
    settings_updated_by: str | None = "root"


async def run_sql(url: URL, statement: str, params: dict[str, Any] | None = None) -> list[Any]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement), params or {})
            return list(result.all()) if result.returns_rows else []
    finally:
        await engine.dispose()


async def seed_legacy(url: URL, data: LegacyData | None = None) -> dict[str, UUID]:
    """LEGACY_HEAD 스키마에 data를 넣고 Deal 코드 -> Deal id 매핑을 돌려준다."""
    data = data or LegacyData()
    customer_id, deal_ids = uuid4(), {}
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as c:
            for user_id, login, display, role, created_by in data.users:
                await c.execute(
                    text(INSERT_USER),
                    {
                        "id": user_id,
                        "login_id": login,
                        "role": role,
                        "display_name": display,
                        "created_by": created_by,
                    },
                )
            await c.execute(text(INSERT_CUSTOMER), {"id": customer_id})
            for code, owner, registrant in data.deals:
                deal_ids[code] = uuid4()
                await c.execute(
                    text(INSERT_DEAL),
                    {
                        "id": deal_ids[code],
                        "code": code,
                        "owner": owner,
                        "registrant": registrant,
                        "customer_id": customer_id,
                    },
                )
            for code, actor in data.actions:
                await c.execute(
                    text(INSERT_ACTION), {"id": uuid4(), "deal_id": deal_ids[code], "actor": actor}
                )
            for code, subject, name in data.changes:
                await c.execute(
                    text(INSERT_CHANGE),
                    {"id": uuid4(), "deal_id": deal_ids[code], "subject": subject, "name": name},
                )
            for number, subject in enumerate(data.sessions):
                await c.execute(
                    text(INSERT_SESSION),
                    {"id": uuid4(), "token": f"tok-{number}", "subject": subject},
                )
            if data.settings_updated_by is not None:
                await c.execute(text(INSERT_SETTINGS), {"updated_by": data.settings_updated_by})
    finally:
        await engine.dispose()
    return deal_ids


async def snapshot(url: URL) -> dict[str, list[Any]]:
    """LEGACY_HEAD 스키마의 모든 업무 데이터(순서 고정). 중단 후 불변 확인에 쓴다."""
    queries = {
        "users": "select id, login_id, display_name, created_by from users order by login_id",
        "deals": "select id, code, owner, owner_user_id from deals order by code",
        "actions": "select id, actor from deal_actions order by id",
        "changes": "select id, changed_by_subject, changed_by_name from deal_stage_changes"
        " order by id",
        "sessions": "select token_hash, subject from auth_sessions order by token_hash",
        "settings": "select updated_by from directory_settings",
    }
    return {name: await run_sql(url, sql) for name, sql in queries.items()}


async def columns_of(url: URL, table: str) -> set[str]:
    rows = await run_sql(
        url,
        "select column_name from information_schema.columns"
        " where table_schema = 'public' and table_name = :t",
        {"t": table},
    )
    return {str(r[0]) for r in rows}
