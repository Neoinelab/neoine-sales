"""head 스키마에 원시 SQL로 계약·계약 첨부 행을 넣는 도우미(license_contracts 외 1).

제약 검증용이라 도메인 검사를 거치지 않는다. 계약은 `deal_code`로 Deal을 찾아 `deal_id`를 채운다
(없는 Deal을 가리키려면 `deal_id=`를 덮어쓴다). 사용자·Deal은 `head_rows`의 도우미로 먼저 만든다.
"""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import text

from tests.support.head_rows import deal_id_of
from tests.support.ids import new_id

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INSERT_CONTRACT = (
    "insert into license_contracts (id, deal_id, status, license_start, license_end,"
    " term_amount, term_unit, tech_owner, inspection_cycle, note, renewed_from_id, ended_at,"
    " created_by_user_id, updated_by_user_id, created_at, updated_at) values (:id, :deal_id,"
    " :status, :license_start, :license_end, :term_amount, :term_unit, :tech_owner,"
    " :inspection_cycle, :note, :renewed_from_id, :ended_at, :user_id, :user_id, now(), now())"
)
INSERT_CONTRACT_ATTACHMENT = (
    "insert into license_contract_attachments (id, contract_id, file_name, description, mime,"
    " size_bytes, storage_key, uploaded_by_user_id, uploaded_at, created_at, updated_at)"
    " values (:id, :contract_id, :file_name, :description, :mime, :size_bytes, :storage_key,"
    " :uploader, now(), now(), now())"
)


async def insert_contract(
    session: AsyncSession,
    deal_code: str,
    user_id: int,
    **overrides: Any,  # noqa: ANN401 - 열 값 덮어쓰기
) -> int:
    """미발급 계약 한 행(기본값은 모든 제약을 통과한다). 새 계약 id를 돌려준다.

    overrides: id, deal_id, status, license_start, license_end(date 또는 None), term_amount,
    term_unit, tech_owner, inspection_cycle, note, renewed_from_id, ended_at.
    """
    values: dict[str, Any] = {
        "id": new_id(),
        "deal_id": await deal_id_of(session, deal_code),
        "status": "not_issued",
        "license_start": None,
        "license_end": None,
        "term_amount": None,
        "term_unit": None,
        "tech_owner": "",
        "inspection_cycle": "none",
        "note": "",
        "renewed_from_id": None,
        "ended_at": None,
        "user_id": user_id,
    }
    values.update(overrides)
    await session.execute(text(INSERT_CONTRACT), values)
    return int(values["id"])


async def insert_issued_contract(
    session: AsyncSession,
    deal_code: str,
    user_id: int,
    **overrides: Any,  # noqa: ANN401
) -> int:
    """발급(신규) 계약 한 행: 2026-01-01부터 1년(종료 2026-12-31)."""
    from datetime import date  # noqa: PLC0415

    values: dict[str, Any] = {
        "status": "issued_new",
        "license_start": date(2026, 1, 1),
        "license_end": date(2026, 12, 31),
        "term_amount": 1,
        "term_unit": "year",
        **overrides,
    }
    return await insert_contract(session, deal_code, user_id, **values)


async def insert_contract_attachment(
    session: AsyncSession,
    contract_id: int,
    uploader: int,
    **overrides: Any,  # noqa: ANN401
) -> int:
    """계약 첨부 한 행. 새 첨부 id를 돌려준다. overrides는 INSERT 파라미터를 덮어쓴다."""
    params: dict[str, Any] = {
        "id": new_id(),
        "contract_id": contract_id,
        "file_name": "a.pdf",
        "description": "",
        "mime": "application/pdf",
        "size_bytes": 10,
        "storage_key": uuid4().hex,
        "uploader": uploader,
    }
    params.update(overrides)
    await session.execute(text(INSERT_CONTRACT_ATTACHMENT), params)
    return int(params["id"])
