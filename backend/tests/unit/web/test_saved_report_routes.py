"""저장 리포트 라우터 (AC1, AC4, AC6, AC7, AC9, AC10, AC19, AC20): FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·권한·응답 모양을 확인한다. 실제 DB를 지나는 시나리오는 functional(reports/)이
맡는다. 조회 결과는 Fake `ReportQueryRunner`가 돌려주는 고정 값이다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.report.catalog import FIELD_CATALOG
from tests.factories_report import make_broken_report
from tests.fakes.report_runner import RENDERED_SQL
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MISSING_ID
from tests.unit.web.saved_report_http import (
    DETAIL_KEYS,
    SUMMARY_KEYS,
    URL,
    VALID_DEFINITION,
    clients,
    create,
    create_body,
    problem,
    update_body,
)

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


# ---- 만들기 (AC1) ----


async def test_create_returns_201_location_and_detail() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(
            URL, json=create_body("Vendor 합계", description="설명", visibility="private")
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["location"] == f"{URL}/{body['id']}"
    assert set(body) == DETAIL_KEYS  # chart·SQL 입력 칸은 없다
    assert (body["name"], body["description"], body["visibility"]) == (
        "Vendor 합계",
        "설명",
        "private",
    )
    assert body["revision"] == 1
    assert body["owner"]["id"] == body["updated_by"]["id"]
    assert body["owner"]["label"] == "사용자 alice"
    assert body["entities"] == ["deal"]
    assert body["generated_sql"] == RENDERED_SQL
    assert body["definition"] == {
        "columns": [
            {
                "field": "deal.code",
                "label": None,
                "format": None,
                "prefix_length": None,
                "group": False,
                "aggregate": None,
            }
        ],
        "conditions": [],
        "combine": "and",
        "sort": None,
        "row_limit": 1000,
    }
    assert body["created_at"].endswith("+09:00")
    assert body["updated_at"].endswith("+09:00")


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_post_put_and_delete_reports(role: Role) -> None:
    async with clients(FakeUseCases(), {"alice": role}) as c:
        made = await create(c["alice"])
        updated = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1))
        deleted = await c["alice"].delete(f"{URL}/{made['id']}")

    assert updated.status_code == 200, updated.text
    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""


async def test_the_generated_sql_cannot_be_sent_by_the_client() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json={**create_body(), "generated_sql": "DROP"})

    problem(response, 422, "request-validation")


# ---- 목록과 보기 (AC4, AC5) ----


async def test_list_returns_summaries_with_user_refs() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], "내 리포트")
        listed = await c["alice"].get(URL)
        await use_cases.resign_user(made["owner"]["id"])
        after = await c["bob"].get(URL)

    assert listed.status_code == 200, listed.text
    (item,) = listed.json()
    assert set(item) == SUMMARY_KEYS
    assert item["id"] == made["id"]
    assert item["owner"]["label"] == "사용자 alice"
    assert item["updated_by"]["id"] == item["owner"]["id"]
    assert item["entities"] == ["deal"]
    assert item["updated_at"].endswith("+09:00")
    (resigned,) = after.json()  # 퇴사해도 공개 리포트는 남는다
    assert resigned["owner"]["label"] == "사용자 alice(퇴사)"
    assert resigned["owner"]["resigned"] is True
    assert resigned["updated_by"]["label"] == "사용자 alice(퇴사)"


async def test_list_shows_only_visible_reports_and_admin_sees_all() -> None:
    async with clients(
        FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER, "root": Role.ADMIN}
    ) as c:
        private = await create(c["alice"], "비공개", visibility="private")
        public = await create(c["alice"], "공개", visibility="public")
        bob = [i["id"] for i in (await c["bob"].get(URL)).json()]
        alice = [i["id"] for i in (await c["alice"].get(URL)).json()]
        admin = [i["id"] for i in (await c["root"].get(URL)).json()]

    assert bob == [public["id"]]
    assert alice == [public["id"], private["id"]]  # 같은 시각이면 id 내림차순
    assert admin == [public["id"], private["id"]]


async def test_get_returns_the_detail_of_a_visible_report() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], "공개", visibility="public")
        response = await c["bob"].get(f"{URL}/{made['id']}")

    assert response.status_code == 200, response.text
    assert response.json() == made


async def test_get_of_a_hidden_report_equals_get_of_a_missing_one() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        hidden = await create(c["alice"], "비공개", visibility="private")
        hidden_response = await c["bob"].get(f"{URL}/{hidden['id']}")
        missing_response = await c["bob"].get(f"{URL}/{MISSING_ID}")

    hidden_body = problem(hidden_response, 404, "not-found")
    missing_body = problem(missing_response, 404, "not-found")
    assert hidden_body["detail"] == missing_body["detail"] == "리포트를 찾을 수 없습니다."


# ---- 수정 (AC7, AC8) ----


async def test_put_updates_the_report_and_bumps_the_revision() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], "원본", visibility="public")
        response = await c["bob"].put(
            f"{URL}/{made['id']}",
            json=update_body(1, "수정본", description="새 설명", visibility="public"),
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["description"], body["revision"]) == ("수정본", "새 설명", 2)
    assert body["owner"]["label"] == "사용자 alice"  # 만든 사람은 그대로
    assert body["updated_by"]["label"] == "사용자 bob"
    assert reread.json() == body


async def test_put_with_a_stale_revision_is_409_invalid_state() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        first = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1, "첫째"))
        stale = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1, "둘째"))
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert first.status_code == 200
    body = problem(stale, 409, "invalid-state")
    assert str(body["detail"]).startswith("다른 사용자가 먼저 이 리포트를 저장했습니다")
    assert reread.json()["name"] == "첫째"


async def test_put_by_a_non_owner_changing_visibility_is_403_forbidden() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], visibility="public")
        response = await c["bob"].put(
            f"{URL}/{made['id']}", json=update_body(1, visibility="private")
        )

    body = problem(response, 403, "forbidden")
    assert body["detail"] == "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."


async def test_put_of_others_private_report_is_404_even_with_a_wrong_revision() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], visibility="private")
        response = await c["bob"].put(f"{URL}/{made['id']}", json=update_body(99))

    problem(response, 404, "not-found")


async def test_renaming_to_a_name_the_owner_already_uses_is_409_already_exists() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        await create(c["alice"], "기존", visibility="public")
        target = await create(c["alice"], "대상", visibility="public")
        response = await c["bob"].put(f"{URL}/{target['id']}", json=update_body(1, "기존"))

    body = problem(response, 409, "already-exists")
    assert body["detail"] == "같은 이름의 리포트가 이미 있습니다."


# ---- 삭제 (AC9) ----


async def test_delete_removes_the_report() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        deleted = await c["alice"].delete(f"{URL}/{made['id']}")
        after = await c["alice"].get(f"{URL}/{made['id']}")

    assert deleted.status_code == 204
    problem(after, 404, "not-found")


async def test_delete_of_others_public_report_is_403_and_admin_delete_is_204() -> None:
    async with clients(
        FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES, "root": Role.ADMIN}
    ) as c:
        made = await create(c["alice"], visibility="public")
        denied = await c["bob"].delete(f"{URL}/{made['id']}")
        still = await c["bob"].get(f"{URL}/{made['id']}")
        allowed = await c["root"].delete(f"{URL}/{made['id']}")

    body = problem(denied, 403, "forbidden")
    assert body["detail"] == "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."
    assert still.status_code == 200
    assert allowed.status_code == 204


async def test_delete_of_others_private_report_is_404() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], visibility="private")
        response = await c["bob"].delete(f"{URL}/{made['id']}")

    problem(response, 404, "not-found")


# ---- 복제 (AC10) ----


async def test_copy_returns_201_location_and_a_new_report_owned_by_the_requester() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        source = await create(c["alice"], "원본", visibility="public")
        response = await c["bob"].post(
            f"{URL}/{source['id']}/copy",
            json={"name": "원본 복사본", "description": "복사", "visibility": "private"},
        )

    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["location"] == f"{URL}/{body['id']}"
    assert body["id"] != source["id"]
    assert (body["name"], body["description"], body["visibility"]) == (
        "원본 복사본",
        "복사",
        "private",
    )
    assert body["owner"]["label"] == "사용자 bob"
    assert body["revision"] == 1
    assert body["definition"] == source["definition"]


async def test_copy_description_defaults_to_empty() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        source = await create(c["alice"], "원본")
        response = await c["alice"].post(
            f"{URL}/{source['id']}/copy", json={"name": "복사", "visibility": "public"}
        )

    assert response.status_code == 201, response.text
    assert response.json()["description"] == ""


async def test_copy_with_a_name_the_requester_already_uses_is_409() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        source = await create(c["alice"], "원본")
        response = await c["alice"].post(
            f"{URL}/{source['id']}/copy", json={"name": "원본", "visibility": "public"}
        )

    problem(response, 409, "already-exists")


async def test_copy_of_a_hidden_report_is_404() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        source = await create(c["alice"], "비공개", visibility="private")
        response = await c["bob"].post(
            f"{URL}/{source['id']}/copy", json={"name": "복사", "visibility": "public"}
        )

    problem(response, 404, "not-found")


# ---- 실행 (AC6) ----


async def test_run_returns_the_query_response_shape() -> None:
    use_cases = FakeUseCases()
    use_cases.uow.reports.respond_with([["20261016-0001"]], total_count=7, sql="SELECT demo")
    async with clients(use_cases, {"alice": Role.USER}) as c:
        made = await create(c["alice"])
        run = await c["alice"].post(f"{URL}/{made['id']}/run")
        query = await c["alice"].post(f"{URL}/query", json=VALID_DEFINITION)

    assert run.status_code == 200, run.text
    assert run.json() == query.json()  # 같은 정의를 /query로 보낸 응답과 같다
    assert run.json()["rows"] == [["20261016-0001"]]
    assert run.json()["sql"] == "SELECT demo"


async def test_run_of_a_hidden_report_is_404() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], visibility="private")
        response = await c["bob"].post(f"{URL}/{made['id']}/run")

    problem(response, 404, "not-found")


async def test_run_timeout_is_503_report_timeout() -> None:
    from app.application.ports.report_query_runner import ReportQueryTimeoutError  # noqa: PLC0415

    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        use_cases.uow.reports.error = ReportQueryTimeoutError()
        response = await c["alice"].post(f"{URL}/{made['id']}/run")

    problem(response, 503, "report-timeout")


# ---- 라우트 순서와 경로 id (AC20) ----


async def test_fields_route_still_wins_over_report_id() -> None:
    async with clients(FakeUseCases(), {"alice": Role.USER}) as c:
        response = await c["alice"].get(f"{URL}/fields")

    assert response.status_code == 200, response.text
    assert [f["key"] for f in response.json()["fields"]] == [f.key for f in FIELD_CATALOG]


async def test_query_route_still_works_beside_the_saved_report_routes() -> None:
    async with clients(FakeUseCases(), {"alice": Role.USER}) as c:
        response = await c["alice"].post(f"{URL}/query", json=VALID_DEFINITION)

    assert response.status_code == 200, response.text


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", str(2**53)])
async def test_malformed_report_ids_are_request_validation(bad_id: str) -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].get(f"{URL}/{bad_id}")

    problem(response, 422, "request-validation")


# ---- 로그인·CSRF ----


async def test_every_saved_report_route_requires_login() -> None:
    async with clients(FakeUseCases(), {"anon": Role.USER}) as c:
        calls = [
            await c["anon"].get(URL),
            await c["anon"].post(URL, json=create_body()),
            await c["anon"].get(f"{URL}/{MISSING_ID}"),
            await c["anon"].put(f"{URL}/{MISSING_ID}", json=update_body()),
            await c["anon"].delete(f"{URL}/{MISSING_ID}"),
            await c["anon"].post(
                f"{URL}/{MISSING_ID}/copy", json={"name": "x", "visibility": "public"}
            ),
            await c["anon"].post(f"{URL}/{MISSING_ID}/run"),
        ]

    for response in calls:
        problem(response, 401, "unauthenticated")


async def test_writes_without_the_csrf_header_are_403_csrf() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}, csrf=False) as c:
        created = await c["alice"].post(URL, json=create_body())
        deleted = await c["alice"].delete(f"{URL}/{MISSING_ID}")

    problem(created, 403, "csrf")
    problem(deleted, 403, "csrf")


# ---- 이름은 모든 리포트 사이에서 고유 (계획 11.1) ----


async def test_create_with_a_name_of_another_users_private_report_is_409() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        await create(c["alice"], "Sales", visibility="private")
        response = await c["bob"].post(URL, json=create_body("sales"))

    body = problem(response, 409, "already-exists")
    assert body["detail"] == "같은 이름의 리포트가 이미 있습니다."


async def test_copy_with_a_name_of_another_users_report_is_409() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        source = await create(c["alice"], "원본", visibility="public")
        await create(c["alice"], "남의 이름", visibility="private")
        response = await c["bob"].post(
            f"{URL}/{source['id']}/copy", json={"name": "남의 이름", "visibility": "public"}
        )

    problem(response, 409, "already-exists")


# ---- 깨진 저장 정의 (계획 11.2) ----


async def _broken(use_cases: FakeUseCases, owner: str, **overrides: str) -> int:
    report = make_broken_report(owner=await use_cases.user_id_of(owner), **overrides)
    async with use_cases.uow as uow:
        await uow.saved_reports.add(report)
        await uow.commit()
    return int(report.id)


async def test_list_succeeds_with_a_broken_report_and_shows_empty_entities() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice", name="깨짐")
        await create(c["alice"], "정상")
        response = await c["alice"].get(URL)

    assert response.status_code == 200, response.text
    by_name = {item["name"]: item for item in response.json()}
    assert by_name["깨짐"]["id"] == broken_id
    assert by_name["깨짐"]["entities"] == []
    assert by_name["정상"]["entities"] == ["deal"]


async def test_others_private_broken_report_is_404_on_get() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "bob", visibility="private")
        listed = await c["alice"].get(URL)
        response = await c["alice"].get(f"{URL}/{broken_id}")

    assert listed.json() == []
    problem(response, 404, "not-found")


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("get", "", None),
        ("post", "/run", None),
        ("post", "/copy", {"name": "복사", "visibility": "public"}),
    ],
)
async def test_broken_report_get_run_copy_are_422_stored_invalid(
    method: str, suffix: str, body: dict[str, str] | None
) -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice")
        response = await c["alice"].request(method, f"{URL}/{broken_id}{suffix}", json=body)

    problem_body = problem(response, 422, "invalid-report")
    assert [(e["location"], e["code"]) for e in problem_body["errors"]] == [
        (["definition"], "stored-invalid")
    ]


async def test_put_with_a_new_definition_repairs_a_broken_report() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice")
        updated = await c["alice"].put(f"{URL}/{broken_id}", json=update_body(1, "복구됨"))
        reread = await c["alice"].get(f"{URL}/{broken_id}")

    assert updated.status_code == 200, updated.text
    assert reread.status_code == 200, reread.text
    assert reread.json()["definition"]["columns"][0]["field"] == "deal.code"
    assert reread.json()["revision"] == 2


async def test_delete_removes_a_broken_report() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice")
        deleted = await c["alice"].delete(f"{URL}/{broken_id}")
        listed = await c["alice"].get(URL)

    assert deleted.status_code == 204
    assert listed.json() == []


# ---- 예전 포맷 요청은 거절 (2026-10-28) ----


@pytest.mark.parametrize("legacy", ["as_is", "prefix", "name", "key"])
async def test_create_and_update_with_legacy_format_are_rejected(legacy: str) -> None:
    definition = {"columns": [{"field": "deal.name", "format": legacy}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        created = await c["alice"].post(URL, json=create_body("새것", definition=definition))
        updated = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, definition=definition)
        )

    for response in (created, updated):
        body = problem(response, 422, "invalid-report")
        assert [(e["location"], e["code"]) for e in body["errors"]] == [
            (["columns", 0, "format"], "format-not-allowed")
        ]
