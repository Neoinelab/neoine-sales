"""head 스키마(BIGINT id)에 원시 SQL로 reports 행을 넣는 도우미.

제약 검증용이라 도메인 검사를 거치지 않는다. 사용자 행은 `head_rows.insert_user`로 만든다.
"""

import json
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_REPORT = (
    "insert into reports (id, name, description, visibility, owner_user_id, updated_by_user_id,"
    " definition, generated_sql, chart, revision, created_at, updated_at)"
    " values (:id, :name, :description, :visibility, :owner_user_id, :updated_by_user_id,"
    " cast(:definition as jsonb), :generated_sql, null, :revision, now(), now())"
)
VALID_DEFINITION = json.dumps({"columns": [{"field": "deal.code"}]})


async def insert_report(
    session: AsyncSession,
    owner_user_id: int,
    **overrides: Any,  # noqa: ANN401 - 열 값 덮어쓰기
) -> int:
    """리포트 한 행. 기본값은 모든 제약을 통과한다. 새 id를 돌려준다.

    overrides: id, name, description, visibility, updated_by_user_id, definition(JSON 문자열),
    generated_sql, revision.
    """
    values: dict[str, Any] = {
        "id": new_id(),
        "name": "리포트",
        "description": "",
        "visibility": "public",
        "owner_user_id": owner_user_id,
        "updated_by_user_id": overrides.get("updated_by_user_id", owner_user_id),
        "definition": VALID_DEFINITION,
        "generated_sql": "SELECT 1",
        "revision": 1,
    }
    values.update(overrides)
    await session.execute(text(INSERT_REPORT), values)
    return int(values["id"])
