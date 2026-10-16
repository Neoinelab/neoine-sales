"""CodeRepository.lock_kind 계약(Major 1): Fake와 SQL 구현에 같은 테스트를 적용한다.

`lock_kind(kind)`는 트랜잭션이 끝날 때까지(commit/rollback) 그 종류의 코드 쓰기를 직렬화하는 배타
잠금이다. 행이 아니라 종류 단위라서 아직 없는 행(새 INSERT)의 경쟁도 막는다. 두 세션이 겹치는
동작(기다림·해제·종류별 독립)은 SQL에서만 의미가 있어 `test_code_lock_kind_sessions.py`가 본다.
여기서는 한 세션에서 지킬 계약만 본다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest

from app.domain.code.values import CodeKind
from tests.factories_catalog import make_code

if TYPE_CHECKING:
    from tests.unit.repositories.catalog_case import CatalogCase

TIMEOUT = 5


@pytest.mark.parametrize("kind", list(CodeKind))
async def test_lock_kind_returns_nothing_for_every_kind(
    catalog: CatalogCase, kind: CodeKind
) -> None:
    result = await asyncio.wait_for(catalog.codes.lock_kind(kind), TIMEOUT)

    assert result is None


async def test_lock_kind_does_not_change_the_rows(catalog: CatalogCase) -> None:
    code = make_code(CodeKind.STATUS, key="zz_s", name="ZZ S", order=10)
    await catalog.codes.add(code)
    before = await catalog.codes.list(CodeKind.STATUS)

    await asyncio.wait_for(catalog.codes.lock_kind(CodeKind.STATUS), TIMEOUT)

    assert list(await catalog.codes.list(CodeKind.STATUS)) == list(before)


async def test_lock_kind_can_be_taken_twice_in_one_transaction(catalog: CatalogCase) -> None:
    """같은 트랜잭션이 이미 쥔 잠금을 다시 요청해도 스스로를 기다리지 않는다."""
    await asyncio.wait_for(catalog.codes.lock_kind(CodeKind.FORECAST), TIMEOUT)

    await asyncio.wait_for(catalog.codes.lock_kind(CodeKind.FORECAST), TIMEOUT)


async def test_writes_still_work_while_the_kind_lock_is_held(catalog: CatalogCase) -> None:
    """잠금을 쥔 트랜잭션 자신은 그 종류에 쓸 수 있다."""
    await asyncio.wait_for(catalog.codes.lock_kind(CodeKind.STATUS), TIMEOUT)
    code = make_code(CodeKind.STATUS, key="zz_locked", name="ZZ Locked", order=11)

    await catalog.codes.add(code)

    assert (await catalog.codes.get(code.id)).name == "ZZ Locked"
