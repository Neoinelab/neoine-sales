"""첨부 파일 feature의 step(P2b R2): 업로드·목록·단건·다운로드·삭제, 디스크 확인, 이력.

Given은 공개 API로 사전 상태를 만든다(저장 위치는 최초 설정에서 등록한 `api.storage_root`,
tmp_path 아래 실제 디렉터리). 여러 사용자가 나오는 시나리오는 사용자마다 로그인 세션(`Session`)을
따로 들고 요청한다(`steps/users.py`). When은 HTTP API 하나, Then은 응답과 다시 조회한 결과,
저장 디렉터리의 실제 파일만 본다.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from tests.functional.steps.actions import given_deal_with_a_sales_owner
from tests.functional.steps.auth import storage_path_of
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import DEALS, history_rows, when_list_history
from tests.functional.steps.login_db import sql_rows
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api
    from tests.functional.steps.users import Session

ATTACHMENTS: Final = "/api/v1/attachments"
GAP_SECONDS: Final = 60  # 동작 사이에 시계를 전진시켜 시각을 구분한다
TARGET: Final = "첨부 파일"
OCTET_STREAM: Final = "application/octet-stream"

READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
DEAL_NOT_FOUND: Final = "Deal을 찾을 수 없습니다."
NOT_FOUND: Final = "첨부 파일을 찾을 수 없습니다."
CONTENT_MISSING: Final = "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."
DELETE_FORBIDDEN: Final = "본인이 올린 파일만 삭제할 수 있습니다."
REPLACE_FORBIDDEN: Final = "본인이 올린 파일만 교체할 수 있습니다."
UPLOAD_UNAVAILABLE: Final = (
    "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."
)
DOWNLOAD_UNAVAILABLE: Final = "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요."
NO_FILE: Final = "업로드할 파일을 선택하세요."
DESCRIPTION_TOO_LONG: Final = "설명은 100자 이내로 입력하세요."
TOO_LARGE: Final = "파일 크기가 100MB를 초과합니다. (최대 100MB)"
INVALID_NAME: Final = "사용할 수 없는 파일 이름입니다."
ATTACHMENT_KEYS: Final = {
    "id",
    "deal_code",
    "file_name",
    "description",
    "size",
    "mime",
    "uploaded_by",
    "uploaded_at",
}


def list_url(code: str) -> str:
    return f"{DEALS}/{code}/attachments"


def item_url(attachment_id: str) -> str:
    return f"{ATTACHMENTS}/{attachment_id}"


def multipart(
    name: str | None = "a.pdf",
    data: bytes = b"hello",
    mime: str = "application/pdf",
    **fields: str,
) -> dict[str, Any]:
    """업로드 multipart 본문. name이 None이면 파일 파트가 없다. fields는 문자 파트."""
    parts: dict[str, Any] = {key: (None, value) for key, value in fields.items()}
    if name is not None:
        parts["file"] = (name, data, mime)
    return parts


def headers_of(session: Session | None) -> dict[str, str] | None:
    return None if session is None else session.headers


# --- Given ---


async def given_deal_with_files_enabled(api: Api) -> str:
    """영업 담당자가 Owner인 Deal의 code(admin 로그인 상태, 저장 위치는 등록되어 있다)."""
    deal = await given_deal_with_a_sales_owner(api)
    return str(deal["code"])


async def given_file(
    api: Api,
    code: str,
    *,
    session: Session | None = None,
    name: str = "a.pdf",
    data: bytes = b"hello",
    **fields: str,
) -> dict[str, Any]:
    """지금 로그인한 사용자(또는 session의 사용자)가 파일을 올려 두었다. 첨부 본문을 돌려준다."""
    response = await when_upload(api, code, session=session, name=name, data=data, **fields)
    assert response.status_code in {200, 201}, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json()["attachment"])


async def given_storage_location_removed(api: Api) -> None:
    """DB에서 저장 위치 설정이 없어진 상태(설정 전 서버에서 이미 만든 Deal 등을 재현)."""
    await sql_rows(api, "delete from storage_settings")


def given_disk_file_removed(api: Api, code: str) -> None:
    """디스크에서 그 Deal의 파일을 모두 지웠다(행은 남아 있다 = 사람이 파일을 옮긴 상황)."""
    for child in (Path(storage_path_of(api)) / code).iterdir():
        child.unlink()


def given_disk_file_unreadable(api: Api, code: str) -> None:
    """디스크 파일을 읽을 수 없게 바꾼다(자기 자신을 가리키는 링크: root에게도 읽기 실패)."""
    for child in (Path(storage_path_of(api)) / code).iterdir():
        child.unlink()
        child.symlink_to(child.name)


def given_disk_file_undeletable(api: Api, code: str) -> None:
    """디스크 파일 자리에 내용이 있는 디렉터리를 둬 파일 삭제가 실패한다(root 사용자에게도 실패)."""
    for child in (Path(storage_path_of(api)) / code).iterdir():
        child.unlink()
        child.mkdir()
        (child / "inside").write_bytes(b"keeps the unlink from working")


async def given_storage_location_moved(api: Api, new_path: str) -> None:
    """관리자가 저장 위치 설정을 다른 경로로 바꿨다(기존 파일은 옮기지 않았다)."""
    await sql_rows(api, "update storage_settings set path = :path", path=new_path)


# --- When (HTTP API 하나) ---


async def when_upload(  # noqa: PLR0913 - 업로드 본문의 독립적인 선택지
    api: Api,
    code: str,
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
        list_url(code),
        files=multipart(name, data, mime, **fields),
        headers=headers_of(session),
    )


async def when_list_attachments(api: Api, code: str, *, session: Session | None = None) -> Response:
    return await api.get(list_url(code), headers=headers_of(session))


async def when_get_attachment(
    api: Api, attachment_id: str, *, session: Session | None = None
) -> Response:
    return await api.get(item_url(attachment_id), headers=headers_of(session))


async def when_download(
    api: Api, attachment_id: str, *, session: Session | None = None
) -> Response:
    return await api.get(f"{item_url(attachment_id)}/download", headers=headers_of(session))


async def when_delete_attachment(
    api: Api, attachment_id: str, *, session: Session | None = None
) -> Response:
    api.clock.advance(GAP_SECONDS)
    return await api.request("DELETE", item_url(attachment_id), headers=headers_of(session))


# --- Then (관찰 가능한 결과) ---


def then_detail_is(response: Response, detail: str) -> None:
    assert response.json()["detail"] == detail, response.json()


def then_upload_is(
    response: Response, *, status: int, outcome: str, name: str | None = None
) -> dict[str, Any] | None:
    """업로드 응답의 상태 코드·결과. 첨부 본문(skipped면 None)을 돌려준다."""
    then_status_is(response, status)
    body = response.json()
    assert set(body) == {"outcome", "attachment"}, body
    assert body["outcome"] == outcome, body
    if outcome == "skipped":
        assert body["attachment"] is None
        return None
    attachment: dict[str, Any] = body["attachment"]
    assert set(attachment) == ATTACHMENT_KEYS, attachment
    if name is not None:
        assert attachment["file_name"] == name
    return attachment


def disk_files(api: Api, code: str) -> list[bytes]:
    """저장 위치 아래 그 Deal 디렉터리의 일반 파일 내용(정렬). 디렉터리가 없으면 빈 목록."""
    directory = Path(storage_path_of(api)) / code
    if not directory.is_dir():
        return []
    return sorted(child.read_bytes() for child in directory.iterdir() if child.is_file())


def then_disk_holds(api: Api, code: str, expected: list[bytes]) -> None:
    assert disk_files(api, code) == sorted(expected)


def then_storage_root_still_exists(api: Api) -> None:
    """저장 위치(root) 디렉터리 자체는 Deal 디렉터리를 지워도 남는다."""
    assert Path(storage_path_of(api)).is_dir()


def then_deal_directory_is_gone(api: Api, code: str) -> None:
    assert not (Path(storage_path_of(api)) / code).exists()


def then_stored_file_is_named_by_a_key(api: Api, code: str, original_name: str) -> None:
    """디스크 파일 이름은 원본 이름이 아니라 32자 소문자 16진수 키다."""
    names = [child.name for child in (Path(storage_path_of(api)) / code).iterdir()]
    assert len(names) == 1, names
    assert len(names[0]) == 32
    assert set(names[0]) <= set("0123456789abcdef")
    assert names[0] != original_name


async def then_row_count_is(api: Api, code: str, count: int) -> None:
    rows = await sql_rows(
        api, "select count(*) from deal_attachments where deal_code = :code", code=code
    )
    assert rows == [(count,)]


async def then_listed_names_are(
    api: Api, code: str, expected: list[str], *, session: Session | None = None
) -> None:
    response = await when_list_attachments(api, code, session=session)
    then_status_is(response, 200)
    assert [item["file_name"] for item in response.json()["items"]] == expected


async def then_attachment_history_is(api: Api, code: str, expected: list[tuple[str, str]]) -> None:
    """첨부 이력(category=attachment)의 (before, after)가 오래된 순서로 expected와 같다."""
    response = await when_list_history(api, code)
    then_status_is(response, 200)
    rows = [row for row in history_rows(response) if row[0] == "attachment"]
    assert all(row[1] == TARGET for row in rows), rows
    assert [(row[2], row[3]) for row in rows] == expected


async def then_deal_updated_at_is_now(api: Api, code: str) -> None:
    """Deal의 수정 시각이 서버 시계의 현재 값(= 방금 한 첨부 동작의 시각)이다."""
    from datetime import datetime  # noqa: PLC0415

    response = await api.get(f"{DEALS}/{code}")
    then_status_is(response, 200)
    assert datetime.fromisoformat(response.json()["updated_at"]) == active_clock().now()


async def then_attachment_is_unchanged(api: Api, before: dict[str, Any]) -> None:
    response = await when_get_attachment(api, str(before["id"]))
    then_status_is(response, 200)
    assert response.json() == before
