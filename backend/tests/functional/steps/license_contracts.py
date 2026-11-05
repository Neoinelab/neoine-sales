"""계약관리(라이선스 계약) feature의 step: 목록·조회·수정·발급·갱신·종료·삭제·첨부, Won 연동.

Given은 공개 API로 사전 상태를 만든다(Deal 등록, Won 진입, 발급). 계약은 Won이 될 때 자동으로
생기므로 수동 등록 API가 없다. When은 HTTP API 하나, Then은 응답과 다시 조회한 결과, 필요하면
DB 행 수·저장 디렉터리의 실제 파일만 본다. 여러 사용자가 나오는 시나리오는 사용자마다 로그인
세션(`Session`)을 따로 들고 요청한다(`steps/users.py`).
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.actions import action_body, actions_url, given_deal_with_a_sales_owner
from tests.functional.steps.attachments import GAP_SECONDS, multipart
from tests.functional.steps.auth import storage_path_of
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import DEALS, given_my_user_id
from tests.functional.steps.login_db import sql_rows

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api
    from tests.functional.steps.users import Session

CONTRACTS: Final = "/api/v1/license-contracts"
CONTRACT_FILES: Final = "/api/v1/license-contract-attachments"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
DELETE_ADMIN_ONLY: Final = "계약 삭제는 관리자만 할 수 있습니다."
ALREADY_ISSUED: Final = "이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다."
NOT_ISSUED_ONLY: Final = "미발급 계약만 발급할 수 있습니다."
ISSUED_ONLY: Final = "발급 상태 계약만 갱신할 수 있습니다."
ALREADY_ENDED: Final = "이미 종료된 계약입니다."
WON_EXIT_BLOCKED: Final = (
    "발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. "
    "계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요."
)
DEAL_NOT_WON: Final = "Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다."
CLOSING: Final = {"revenue_amount": 900_000_000, "revenue_date": "2026-10-20"}
CONTRACT_KEYS: Final = {
    "id",
    "deal_code",
    "deal_name",
    "customer",
    "vendor",
    "product",
    "partner",
    "sales_owner",
    "status",
    "license_start",
    "license_end",
    "term",
    "tech_owner",
    "inspection_cycle",
    "note",
    "renewed_from_id",
    "ended_at",
    "attachment_count",
    "deal_is_won",
    "created_by",
    "updated_by",
    "created_at",
    "updated_at",
}


def contract_url(contract_id: object) -> str:
    return f"{CONTRACTS}/{contract_id}"


def issue_body(
    start: str = "2026-01-01", amount: int = 1, unit: str = "year", **fields: object
) -> dict[str, Any]:
    """발급·갱신 본문(계약 칸 + 시작일·기간)."""
    return {"start_date": start, "term_amount": amount, "term_unit": unit, **fields}


def headers_of(session: Session | None) -> dict[str, str] | None:
    return None if session is None else session.headers


# --- Given ---


async def given_won_deal(api: Api, **overrides: object) -> str:
    """처음부터 Won으로 등록한 Deal의 code(영업 담당자가 Owner, admin 로그인 상태)."""
    deal = await given_deal_with_a_sales_owner(
        api, status_key="contract_completed", forecast_key="won", **overrides
    )
    return str(deal["code"])


async def given_open_deal(api: Api, **overrides: object) -> str:
    """Won이 아닌 Deal의 code(Status prospecting / Forecast pipeline)."""
    deal = await given_deal_with_a_sales_owner(api, **overrides)
    return str(deal["code"])


async def contracts_of(api: Api, code: str) -> list[dict[str, Any]]:
    """그 Deal의 계약 전부(id 오름차순, 목록 API로 읽는다)."""
    response = await api.get(CONTRACTS, params={"limit": 200})
    assert response.status_code == 200, response.text
    found = [item for item in response.json()["items"] if item["deal_code"] == code]
    return sorted(found, key=lambda item: int(item["id"]))


async def given_contract_of(api: Api, code: str) -> dict[str, Any]:
    """그 Deal의 계약 하나(정확히 하나여야 한다)."""
    found = await contracts_of(api, code)
    assert len(found) == 1, f"계약이 하나여야 한다: {found}"
    return found[0]


async def given_issued_contract(
    api: Api, code: str, *, start: str = "2026-01-01", amount: int = 1, unit: str = "year"
) -> dict[str, Any]:
    """Won Deal의 미발급 계약을 발급해 둔 상태의 계약(발급(신규))."""
    contract = await given_contract_of(api, code)
    response = await when_issue(api, contract["id"], start=start, amount=amount, unit=unit)
    assert response.status_code == 200, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


async def given_extra_contract_row(api: Api, code: str) -> dict[str, Any]:
    """그 Deal에 미발급 계약 행이 하나 더 있다(API로는 만들 수 없는 상태라 DB에 직접 넣는다).

    Won 진입은 계약이 없을 때만 하나를 만들고 갱신은 발급 상태 계약만 늘리므로, 같은 Deal에
    발급 계약과 미발급 계약이 함께 있는 상태는 API 흐름으로는 나오지 않는다(발급 유일 규칙 확인용).
    """
    me = await given_my_user_id(api)
    await sql_rows(
        api,
        "insert into license_contracts (deal_id, status, tech_owner, inspection_cycle, note,"
        " created_by_user_id, updated_by_user_id, created_at, updated_at)"
        " select d.id, 'not_issued', '', 'none', '', :me, :me, now(), now()"
        " from deals d where d.deal_code = :code",
        me=me,
        code=code,
    )
    extra = [c for c in await contracts_of(api, code) if c["status"] == "not_issued"]
    assert len(extra) == 1, extra
    return extra[0]


async def given_contract_file(
    api: Api,
    contract_id: object,
    *,
    session: Session | None = None,
    name: str = "a.pdf",
    data: bytes = b"hello",
    **fields: str,
) -> dict[str, Any]:
    """지금 로그인한 사용자(또는 session의 사용자)가 계약에 파일을 올려 두었다. 첨부 본문."""
    response = await when_upload_contract_file(
        api, contract_id, session=session, name=name, data=data, **fields
    )
    assert response.status_code in {200, 201}, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json()["attachment"])


# --- When (HTTP API 하나) ---


async def when_list_contracts(
    api: Api, *, session: Session | None = None, **params: str | int
) -> Response:
    return await api.get(CONTRACTS, params=dict(params), headers=headers_of(session))


async def when_get_contract(
    api: Api, contract_id: object, *, session: Session | None = None
) -> Response:
    return await api.get(contract_url(contract_id), headers=headers_of(session))


async def when_update_contract(
    api: Api, contract_id: object, *, session: Session | None = None, **body: object
) -> Response:
    return await when_update_contract_body(api, contract_id, dict(body), session=session)


async def when_update_contract_body(
    api: Api, contract_id: object, body: dict[str, Any], *, session: Session | None = None
) -> Response:
    return await api.request(
        "PUT", contract_url(contract_id), json=body, headers=headers_of(session)
    )


async def when_issue(  # noqa: PLR0913 - 발급 본문의 독립적인 선택지
    api: Api,
    contract_id: object,
    *,
    session: Session | None = None,
    start: str = "2026-01-01",
    amount: int = 1,
    unit: str = "year",
    **fields: object,
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request(
        "POST",
        f"{contract_url(contract_id)}/issue",
        json=issue_body(start, amount, unit, **fields),
        headers=headers_of(session),
    )


async def when_renew(  # noqa: PLR0913 - 갱신 본문의 독립적인 선택지
    api: Api,
    contract_id: object,
    *,
    session: Session | None = None,
    start: str = "2027-01-01",
    amount: int = 1,
    unit: str = "year",
    **fields: object,
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request(
        "POST",
        f"{contract_url(contract_id)}/renewal",
        json=issue_body(start, amount, unit, **fields),
        headers=headers_of(session),
    )


async def when_end(api: Api, contract_id: object, *, session: Session | None = None) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request(
        "POST", f"{contract_url(contract_id)}/end", headers=headers_of(session)
    )


async def when_delete_contract(
    api: Api, contract_id: object, *, session: Session | None = None
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request("DELETE", contract_url(contract_id), headers=headers_of(session))


async def when_list_contract_files(
    api: Api, contract_id: object, *, session: Session | None = None
) -> Response:
    return await api.get(f"{contract_url(contract_id)}/attachments", headers=headers_of(session))


async def when_upload_contract_file(  # noqa: PLR0913 - 업로드 본문의 독립적인 선택지
    api: Api,
    contract_id: object,
    *,
    session: Session | None = None,
    name: str | None = "a.pdf",
    data: bytes = b"hello",
    mime: str = "application/pdf",
    **fields: str,
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request(
        "POST",
        f"{contract_url(contract_id)}/attachments",
        files=multipart(name, data, mime, **fields),
        headers=headers_of(session),
    )


async def when_download_contract_file(
    api: Api, attachment_id: object, *, session: Session | None = None
) -> Response:
    return await api.get(f"{CONTRACT_FILES}/{attachment_id}/download", headers=headers_of(session))


async def when_delete_contract_file(
    api: Api, attachment_id: object, *, session: Session | None = None
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request(
        "DELETE", f"{CONTRACT_FILES}/{attachment_id}", headers=headers_of(session)
    )


# Deal 쪽 요청(Won 진입·이탈). When으로 쓰인다.


def _flag(delete: bool | None) -> dict[str, object]:
    return {} if delete is None else {"delete_license_contracts": delete}


async def when_enter_won_by_change(api: Api, code: str) -> Response:
    """목록 인라인 변경: Forecast를 Won으로(Status 계약완료가 함께 바뀐다)."""
    body = {"change": {"field": "forecast_key", "value": "won"}, "resolution": CLOSING}
    return await api.post(f"{DEALS}/{code}/changes", json=body)


async def when_leave_won_by_change(
    api: Api, code: str, *, delete: bool | None = None, session: Session | None = None
) -> Response:
    """목록 인라인 변경: Forecast를 Commit으로(Status는 POC완료로 함께 바꾼다)."""
    body = {
        "change": {"field": "forecast_key", "value": "commit"},
        "resolution": {"status_key": "poc_completed"},
        **_flag(delete),
    }
    return await api.request(
        "POST", f"{DEALS}/{code}/changes", json=body, headers=headers_of(session)
    )


async def when_leave_won_by_form(
    api: Api, code: str, *, delete: bool | None = None, session: Session | None = None
) -> Response:
    """Deal 폼 수정: Status·Forecast를 함께 Won 밖으로."""
    body = {"status_key": "poc_completed", "forecast_key": "commit", **_flag(delete)}
    return await api.request("PATCH", f"{DEALS}/{code}", json=body, headers=headers_of(session))


async def when_enter_won_by_form(api: Api, code: str) -> Response:
    return await api.patch(
        f"{DEALS}/{code}", json={"status_key": "contract_completed", "forecast_key": "won"}
    )


async def when_enter_won_by_action(api: Api, code: str) -> Response:
    """Action 등록의 status_changes로 Forecast를 Won으로."""
    api.clock.advance(GAP_SECONDS)
    change = {"change": {"field": "forecast_key", "value": "won"}, "resolution": CLOSING}
    return await api.post(actions_url(code), json=action_body(status_changes=[change]))


async def when_leave_won_by_action(
    api: Api, code: str, *, delete: bool | None = None, session: Session | None = None
) -> Response:
    """Action 등록의 status_changes로 Forecast를 Commit으로(Status는 POC완료로)."""
    api.clock.advance(GAP_SECONDS)
    change = {
        "change": {"field": "forecast_key", "value": "commit"},
        "resolution": {"status_key": "poc_completed"},
    }
    body = action_body(status_changes=[change], **_flag(delete))
    return await api.request("POST", actions_url(code), json=body, headers=headers_of(session))


async def when_delete_deal_with_contracts(api: Api, code: str) -> Response:
    return await api.delete(f"{DEALS}/{code}?confirm_code={code}")


# --- Then (관찰 가능한 결과) ---


def then_contract_has_the_documented_keys(contract: dict[str, Any]) -> None:
    assert set(contract) == CONTRACT_KEYS, contract


async def then_statuses_are(api: Api, code: str, expected: list[str]) -> None:
    """그 Deal 계약의 상태가 id 오름차순으로 expected와 같다."""
    assert [c["status"] for c in await contracts_of(api, code)] == expected


async def then_deal_reports_contract_count(api: Api, code: str, count: int) -> None:
    response = await api.get(f"{DEALS}/{code}")
    then_status_is(response, 200)
    assert response.json()["license_contract_count"] == count, response.json()


async def then_contract_row_count_is(api: Api, code: str, count: int) -> None:
    rows = await sql_rows(
        api,
        "select count(*) from license_contracts c join deals d on d.id = c.deal_id"
        " where d.deal_code = :code",
        code=code,
    )
    assert rows == [(count,)]


async def then_file_row_count_is(api: Api, count: int) -> None:
    rows = await sql_rows(api, "select count(*) from license_contract_attachments")
    assert rows == [(count,)]


async def then_contract_was_created_by_me(api: Api, contract: dict[str, Any]) -> None:
    me = await given_my_user_id(api)
    assert contract["created_by"]["id"] == me
    assert contract["updated_by"]["id"] == me


# --- 디스크: 계약 첨부는 `<저장 위치>/license-contracts/<계약 id>/<key>` ---


def contract_dir(api: Api, contract_id: object) -> Path:
    return Path(storage_path_of(api)) / "license-contracts" / str(contract_id)


def contract_disk_files(api: Api, contract_id: object) -> list[bytes]:
    """그 계약 폴더의 일반 파일 내용(정렬). 폴더가 없으면 빈 목록."""
    directory = contract_dir(api, contract_id)
    if not directory.is_dir():
        return []
    return sorted(child.read_bytes() for child in directory.iterdir() if child.is_file())


def then_contract_disk_holds(api: Api, contract_id: object, expected: list[bytes]) -> None:
    assert contract_disk_files(api, contract_id) == sorted(expected)


def then_contract_folder_exists(api: Api, contract_id: object) -> None:
    assert contract_dir(api, contract_id).is_dir()


def then_contract_folder_is_gone(api: Api, contract_id: object) -> None:
    assert not contract_dir(api, contract_id).exists()


def then_deal_folder_has_no_contract_files(api: Api, code: str) -> None:
    """Deal 폴더(`<저장 위치>/<deal_code>`)에 계약 첨부가 섞여 있지 않다."""
    assert not (Path(storage_path_of(api)) / code / "license-contracts").exists()


def then_contract_file_is_named_by_a_key(api: Api, contract_id: object) -> None:
    """계약 폴더의 파일 이름은 원본 이름이 아니라 32자 소문자 16진수 키 하나다."""
    names = [child.name for child in contract_dir(api, contract_id).iterdir()]
    assert len(names) == 1, names
    assert len(names[0]) == 32
    assert set(names[0]) <= set("0123456789abcdef")
