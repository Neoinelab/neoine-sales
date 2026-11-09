"""계약 첨부 라우터: 업로드 응답, 다운로드 헤더, 역할별 읽기, 없는 id, 저장 위치 오류.

FakeUseCases·FakeFileStorage 위에서 HTTP 계약을 확인한다. 유스케이스 규칙(폴더·권한 판정)은
`tests/unit/application/test_license_contract_*.py`가 맡는다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from tests.support.ids import MISSING_ID
from tests.unit.web.attachment_http import form
from tests.unit.web.license_contract_http import (
    ATTACHMENT_URL,
    ATTACHMENTS,
    BASE,
    clients,
    problem,
    seed_contract,
)

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

ROOT = "/data/neoine-sales/files"
NOT_FOUND_CONTRACT = "라이선스 계약을 찾을 수 없습니다."
NOT_FOUND_FILE = "첨부 파일을 찾을 수 없습니다."
UPLOAD_UNAVAILABLE = "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."
DOWNLOAD_UNAVAILABLE = "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요."
CONTENT_MISSING = "첨부 파일 내용을 찾을 수 없습니다. 관리자에게 문의하세요."
ATTACHMENT_KEYS = {
    "id",
    "contract_id",
    "deal_code",
    "file_name",
    "description",
    "size",
    "mime",
    "uploaded_by",
    "uploaded_at",
}


async def _ready() -> tuple[FakeUseCases, int]:
    """저장 위치가 설정된 FakeUseCases와 그 위의 계약 id."""
    from tests.fakes.use_cases import FakeUseCases  # noqa: PLC0415

    use_cases = FakeUseCases()
    await use_cases.seed_storage(ROOT)
    contract = await seed_contract(use_cases)
    return use_cases, int(contract.id)


async def _put(
    http: AsyncClient,
    contract_id: int,
    name: str = "a.pdf",
    data: bytes = b"hello",
    **fields: str,
) -> Any:  # noqa: ANN401 - httpx Response
    return await http.post(
        ATTACHMENTS.format(id=contract_id), files=form((name, data, "application/pdf"), **fields)
    )


async def test_upload_is_201_with_a_download_location_and_the_attachment() -> None:
    """새 파일을 올리면 201, Location 헤더, `uploaded` 결과와 첨부 정보를 돌려준다.

    테스트 코드: LC-063
    """
    # given: 저장 위치가 있고 미발급 계약이 있다
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: KIM이 "계약서.pdf"(7바이트, 설명 "원본")를 올린다
        response = await _put(c["kim"], contract_id, "계약서.pdf", b"content", description="원본")

    # then: 201 + Location, outcome uploaded, 첨부에 계약 id·이름·크기·설명이 담긴다
    body = response.json()
    assert response.status_code == 201, response.text
    assert body["outcome"] == "uploaded"
    attachment = body["attachment"]
    assert set(attachment) == ATTACHMENT_KEYS
    assert (attachment["contract_id"], attachment["file_name"], attachment["size"]) == (
        contract_id,
        "계약서.pdf",
        7,
    )
    assert attachment["description"] == "원본"
    assert response.headers["location"].endswith(
        ATTACHMENT_URL.format(id=attachment["id"]) + "/download"
    )


async def test_upload_of_a_taken_name_is_409_file_exists_by_default() -> None:
    """같은 이름을 `on_exists` 없이 올리면 409 `file-exists`이고 첨부는 그대로다.

    테스트 코드: LC-064
    """
    # given: "a.pdf"가 이미 올라간 계약
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        await _put(c["kim"], contract_id, "a.pdf", b"old")
        # when: "a.pdf"를 on_exists 없이 다시 올린다
        response = await _put(c["kim"], contract_id, "a.pdf", b"new")
        listed = (await c["kim"].get(ATTACHMENTS.format(id=contract_id))).json()

    # then: 409 file-exists와 문구, 첨부는 1개 그대로
    detail = problem(response, 409, "file-exists")["detail"]
    assert detail == "같은 이름의 파일이 이미 있습니다: a.pdf"
    assert len(listed["items"]) == 1


async def test_upload_with_skip_is_200_skipped_without_an_attachment() -> None:
    """같은 이름을 `on_exists=skip`으로 올리면 200 `skipped`이고 첨부 정보는 null이다.

    테스트 코드: LC-065
    """
    # given: "a.pdf"가 이미 올라간 계약
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        await _put(c["kim"], contract_id, "a.pdf", b"old")
        # when: "a.pdf"를 skip으로 올린다
        response = await _put(c["kim"], contract_id, "a.pdf", b"new", on_exists="skip")

    # then: 200 {outcome: skipped, attachment: null}
    assert response.status_code == 200, response.text
    assert response.json() == {"outcome": "skipped", "attachment": None}


async def test_replace_is_200_for_the_uploader_and_403_for_another_sales() -> None:
    """같은 이름을 교체로 올리면 올린 사람은 200 `replaced`, 다른 sales는 403이다.

    테스트 코드: LC-066
    """
    # given: KIM이 올린 "a.pdf"(old)가 있는 계약
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES, "park": Role.SALES}) as c:
        first = (await _put(c["kim"], contract_id, "a.pdf", b"old")).json()["attachment"]
        # when: PARK가 교체를 시도하고, 이어 KIM이 교체한다
        by_park = await _put(c["park"], contract_id, "a.pdf", b"new", on_exists="replace")
        by_kim = await _put(c["kim"], contract_id, "a.pdf", b"new", on_exists="replace")

    # then: PARK는 403 문구, KIM은 200 replaced에 같은 첨부 id
    detail = problem(by_park, 403, "forbidden")["detail"]
    assert detail == "본인이 올린 파일만 교체할 수 있습니다."
    assert by_kim.status_code == 200, by_kim.text
    assert by_kim.json()["outcome"] == "replaced"
    assert by_kim.json()["attachment"]["id"] == first["id"]


async def test_upload_without_a_file_part_is_422_invalid_value() -> None:
    """파일 파트가 없으면 422 `invalid-value`와 안내 문구다.

    테스트 코드: LC-067
    """
    # given: 저장 위치가 있는 계약
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 파일 파트 없이 올린다
        response = await c["kim"].post(ATTACHMENTS.format(id=contract_id), files=form(None))

    # then: 422 invalid-value "업로드할 파일을 선택하세요."
    assert problem(response, 422, "invalid-value")["detail"] == "업로드할 파일을 선택하세요."


async def test_upload_without_a_storage_location_is_503() -> None:
    """저장 위치 설정이 없으면 업로드는 503 `storage-unavailable`이다.

    테스트 코드: LC-068
    """
    # given: 저장 위치 설정이 없는 상태의 계약
    from tests.fakes.use_cases import FakeUseCases  # noqa: PLC0415

    use_cases = FakeUseCases()
    contract = await seed_contract(use_cases)
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        # when: 파일을 올린다
        response = await _put(c["kim"], int(contract.id))
        listed = (await c["kim"].get(ATTACHMENTS.format(id=contract.id))).json()

    # then: 503 storage-unavailable 문구, 첨부는 생기지 않는다
    assert problem(response, 503, "storage-unavailable")["detail"] == UPLOAD_UNAVAILABLE
    assert listed["items"] == []


@pytest.mark.parametrize("role", [Role.USER, Role.SALES, Role.ADMIN])
async def test_every_role_lists_newest_first_and_downloads_exact_bytes(role: Role) -> None:
    """모든 역할이 첨부 목록을 최신순으로 보고 `octet-stream`·`attachment` 헤더로 내려받는다.

    테스트 코드: LC-074
    """
    # given: "a.pdf"(먼저)와 "b.pdf"(나중)가 올라간 계약
    use_cases, contract_id = await _ready()
    payload = b"\x00\x01binary\xff"
    async with clients(use_cases, {"kim": Role.SALES, "reader": role}) as c:
        first = (await _put(c["kim"], contract_id, "a.pdf", payload)).json()["attachment"]
        second = (await _put(c["kim"], contract_id, "b.pdf", b"b")).json()["attachment"]
        # when: 해당 역할이 목록을 읽고 "a.pdf"를 내려받는다
        listed = (await c["reader"].get(ATTACHMENTS.format(id=contract_id))).json()
        download = await c["reader"].get(ATTACHMENT_URL.format(id=first["id"]) + "/download")

    # then: 목록은 b, a 순이고 다운로드는 정확한 바이트와 헤더다
    assert [item["id"] for item in listed["items"]] == [second["id"], first["id"]]
    assert download.status_code == 200, download.text
    assert download.content == payload
    assert download.headers["content-type"].split(";")[0] == "application/octet-stream"
    assert download.headers["content-disposition"].startswith('attachment; filename="a.pdf"')


async def test_download_without_a_storage_location_is_503() -> None:
    """저장 위치 설정이 없으면 다운로드는 503 `storage-unavailable`이다.

    테스트 코드: LC-075
    """
    # given: 파일이 올라간 뒤 저장 위치 설정이 사라졌다
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        attachment = (await _put(c["kim"], contract_id)).json()["attachment"]
        async with use_cases.uow as uow:
            uow.storage_settings._items.clear()
            await uow.commit()
        # when: 내려받는다
        response = await c["kim"].get(ATTACHMENT_URL.format(id=attachment["id"]) + "/download")

    # then: 503 storage-unavailable 문구
    assert problem(response, 503, "storage-unavailable")["detail"] == DOWNLOAD_UNAVAILABLE


async def test_download_of_a_row_without_its_file_is_404_content_missing() -> None:
    """행은 있는데 계약 폴더에 파일이 없으면 404 "첨부 파일 내용을 찾을 수 없습니다."이다.

    테스트 코드: LC-075
    """
    # given: 행은 있으나 디스크 파일이 없는 첨부
    use_cases, contract_id = await _ready()
    async with clients(use_cases, {"kim": Role.SALES}) as c:
        attachment = (await _put(c["kim"], contract_id)).json()["attachment"]
        use_cases.file_storage._files.clear()  # 디스크 파일만 사라진 상태
        # when: 내려받는다
        response = await c["kim"].get(ATTACHMENT_URL.format(id=attachment["id"]) + "/download")

    # then: 404 not-found 내용 없음 문구
    assert problem(response, 404, "not-found")["detail"] == CONTENT_MISSING


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_missing_attachment_and_contract_ids_are_404_with_their_sentences(role: Role) -> None:
    """없는 첨부 id의 다운로드·삭제와 없는 계약 id의 첨부 목록·업로드는 404이고 문구가 다르다.

    테스트 코드: LC-029
    """
    # given: 아무 계약도 첨부도 없는 상태의 sales 또는 admin
    from tests.fakes.use_cases import FakeUseCases  # noqa: PLC0415

    async with clients(FakeUseCases(), {"someone": role}) as c:
        # when: 없는 첨부 id로 다운로드·삭제, 없는 계약 id로 첨부 목록·업로드를 요청한다
        download = await c["someone"].get(ATTACHMENT_URL.format(id=MISSING_ID) + "/download")
        remove = await c["someone"].delete(ATTACHMENT_URL.format(id=MISSING_ID))
        listed = await c["someone"].get(f"{BASE}/{MISSING_ID}/attachments")
        upload = await _put(c["someone"], MISSING_ID)

    # then: 모두 404 not-found이고 첨부는 첨부 문구, 계약은 계약 문구다
    assert problem(download, 404, "not-found")["detail"] == NOT_FOUND_FILE
    assert problem(remove, 404, "not-found")["detail"] == NOT_FOUND_FILE
    assert problem(listed, 404, "not-found")["detail"] == NOT_FOUND_CONTRACT
    assert problem(upload, 404, "not-found")["detail"] == NOT_FOUND_CONTRACT
