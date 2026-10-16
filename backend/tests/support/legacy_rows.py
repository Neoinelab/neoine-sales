"""과거 리비전 스키마(문자열 사용자 컬럼 시절)에 원시 SQL로 행을 넣는 도우미.

현재 head 스키마용 도우미는 `tests.support.head_rows`다. 여기 함수는 deals.owner / users.created_by
문자열 컬럼이 있는 리비전 전용이라 head에는 쓰지 않는다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def insert_customer(session: AsyncSession, **overrides: object) -> str:
    values: dict[str, object] = {
        "id": uuid4(),
        "company_name": "회사",
        "contact_name": "담당",
        "notes": "",
        "employee_count": None,
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into customers (id, company_name, contact_name, notes, employee_count,"
            " created_at, updated_at) values (:id, :company_name, :contact_name, :notes,"
            " :employee_count, now(), now())"
        ),
        values,
    )
    return str(values["id"])


async def insert_legacy_deal(session: AsyncSession, customer_id: str, **overrides: object) -> None:
    """과거 리비전(deals.owner 문자열 컬럼 시절) 스키마 전용."""
    values: dict[str, object] = {
        "id": uuid4(),
        "code": "D-1",
        "customer_id": customer_id,
        "amount": 100,
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into deals (id, code, name, owner, vendor, solution, revenue_amount,"
            " revenue_currency, revenue_date, customer_id, created_at, updated_at)"
            " values (:id, :code, 'n', 'o', 'v', 's', :amount, 'KRW', current_date,"
            " :customer_id, now(), now())"
        ),
        values,
    )


async def insert_legacy_user(
    session: AsyncSession, login_id: str = "kim", **overrides: object
) -> None:
    """과거 리비전(users.created_by 문자열 컬럼 시절) 스키마 전용."""
    values: dict[str, object] = {
        "id": uuid4(),
        "login_id": login_id,
        "role": "sales",
        "created_by": "admin",
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into users (id, login_id, role, created_by, created_at, updated_at)"
            " values (:id, :login_id, :role, :created_by, now(), now())"
        ),
        values,
    )
