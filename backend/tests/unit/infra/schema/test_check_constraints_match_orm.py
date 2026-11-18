"""head DB의 CHECK 제약이 ORM이 선언한 CHECK와 같은 허용 값을 가진다(운영 500 재발 방지)."""

import re
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.deal.history import HistoryCategory
from app.infra.db import models  # noqa: F401 - 메타데이터 등록
from app.infra.db.base import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

_LITERAL = re.compile(r"'((?:[^']|'')*)'")


def _literals(expression: str) -> frozenset[str]:
    """식 안의 문자열 리터럴 집합(순서·공백·캐스트 표기 차이를 무시한다)."""
    return frozenset(_LITERAL.findall(expression))


async def _db_checks(url: URL) -> dict[str, str]:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    "select conname, pg_get_constraintdef(oid) from pg_constraint "
                    "where contype = 'c' and connamespace = 'public'::regnamespace"
                )
            )
            return {str(name): definition for name, definition in rows}
    finally:
        await engine.dispose()


async def test_deal_history_accepts_every_history_category_value(
    test_database_url: URL,
) -> None:
    """deal_history의 category CHECK가 HistoryCategory의 모든 값을 허용한다.

    테스트 코드: SC-059

    given: head를 적용한 임시 DB
    """
    # when: DB의 ck_deal_history_category 식을 읽는다
    checks = await _db_checks(test_database_url)
    allowed = _literals(checks["ck_deal_history_category"])

    # then: 허용 집합이 enum의 모든 값(특히 comment)과 정확히 같다
    assert allowed == {c.value for c in HistoryCategory}


async def test_every_orm_check_constraint_has_same_allowed_literals_in_head_db(
    test_database_url: URL,
) -> None:
    """ORM이 선언한 모든 CHECK의 문자열 리터럴 집합이 head DB의 같은 이름 CHECK와 같다.

    테스트 코드: SC-060
    """
    # given: ORM 메타데이터의 CHECK 식(이름 → 리터럴 집합)
    expected: dict[str, frozenset[str]] = {}
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and constraint.name is not None:
                literals = _literals(str(constraint.sqltext))
                if literals:  # 숫자 범위 식은 PG가 리터럴로 다시 쓰므로 제외
                    expected[str(constraint.name)] = literals

    # when: head DB의 CHECK 식을 읽는다
    actual = {name: _literals(d) for name, d in (await _db_checks(test_database_url)).items()}

    # then: 이름별 리터럴 집합이 같다
    mismatched = {
        name: (sorted(literals), sorted(actual.get(name, frozenset())))
        for name, literals in expected.items()
        if literals != actual.get(name, frozenset())
    }
    assert mismatched == {}
