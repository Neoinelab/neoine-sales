"""저장 리포트 라우터: FakeUseCases 위의 HTTP 계약.

DB 없이 라우터·스키마·권한·응답 모양을 확인한다. 조회 결과는 Fake `ReportQueryRunner`가 돌려주는
고정 값이다.
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


# ---- 만들기 ----


async def test_create_returns_201_location_and_detail() -> None:
    """리포트를 만들면 201과 Location, 상세 응답(revision 1, 만든 사람 = 최종 수정자)이다.

    테스트 코드: RS-001
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 비공개 리포트를 만든다
        response = await c["alice"].post(
            URL, json=create_body("Vendor 합계", description="설명", visibility="private")
        )
    # then: 201과 Location이고 응답은 상세 키 전부를 가진다(SQL 입력 칸은 없다)
    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["location"] == f"{URL}/{body['id']}"
    assert set(body) == DETAIL_KEYS
    assert (body["name"], body["description"], body["visibility"]) == (
        "Vendor 합계",
        "설명",
        "private",
    )
    # then: revision 1, 만든 사람 = 최종 수정자, 생성 시각 = 수정 시각, 서버 오프셋 시각이다
    assert body["revision"] == 1
    assert body["owner"]["id"] == body["updated_by"]["id"]
    assert body["owner"]["label"] == "사용자 alice"
    assert body["created_at"] == body["updated_at"]
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
                "sort": None,
            }
        ],
        "conditions": [],
        "combine": "and",
        "row_limit": 1000,
    }
    assert body["created_at"].endswith("+09:00")
    assert body["updated_at"].endswith("+09:00")


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_can_post_put_and_delete_reports(role: Role) -> None:
    """admin·sales·user 모두 만들기·덮어쓰기·삭제가 역할 가드에 막히지 않는다.

    테스트 코드: RS-050
    """
    # given: 역할별 로그인 사용자
    async with clients(FakeUseCases(), {"alice": role}) as c:
        # when: 만들고 덮어쓰고 지운다
        made = await create(c["alice"])
        updated = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1))
        deleted = await c["alice"].delete(f"{URL}/{made['id']}")
    # then: 200, 204(본문 없음)이다
    assert updated.status_code == 200, updated.text
    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""


async def test_the_generated_sql_cannot_be_sent_by_the_client() -> None:
    """본문에 SQL 같은 모르는 키를 보내면 422 request-validation이고 목록은 비어 있다.

    테스트 코드: RS-003
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: generated_sql을 더한 본문으로 만든다
        response = await c["alice"].post(URL, json={**create_body(), "generated_sql": "DROP"})
        listed = await c["alice"].get(URL)
    # then: 422 request-validation이고 저장되지 않는다
    problem(response, 422, "request-validation")
    assert listed.json() == []


# ---- 목록과 보기 ----


async def test_list_returns_summaries_with_user_refs() -> None:
    """목록 항목은 정해진 키만 갖고 사용자는 UserRef이며, 퇴사한 만든 사람은 "(퇴사)"로 보인다.

    테스트 코드: RS-010, RS-048
    """
    # given: alice의 공개 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], "내 리포트")
        # when: alice가 목록을 읽는다
        listed = await c["alice"].get(URL)
        # then: 항목 키는 요약 키이고(정의·배치 없음) 사용자 표시와 서버 오프셋 시각이 있다
        assert listed.status_code == 200, listed.text
        (item,) = listed.json()
        assert set(item) == SUMMARY_KEYS
        assert item["id"] == made["id"]
        assert item["owner"]["label"] == "사용자 alice"
        assert item["updated_by"]["id"] == item["owner"]["id"]
        assert item["entities"] == ["deal"]
        assert item["updated_at"].endswith("+09:00")
        # given: alice가 퇴사 처리됨
        await use_cases.resign_user(made["owner"]["id"])
        # when: bob이 목록을 읽는다
        after = await c["bob"].get(URL)
    # then: 공개 리포트는 남고 만든 사람·최종 수정자가 "(퇴사)"로 보인다
    (resigned,) = after.json()
    assert resigned["owner"]["label"] == "사용자 alice(퇴사)"
    assert resigned["owner"]["resigned"] is True
    assert resigned["updated_by"]["label"] == "사용자 alice(퇴사)"


async def test_list_shows_only_visible_reports_and_admin_sees_all() -> None:
    """목록은 공개·자기 리포트만 보여 주고 admin에게는 비공개도 보인다(동률은 id 내림차순).

    테스트 코드: RS-010, RS-011
    """
    # given: alice의 비공개·공개 리포트
    async with clients(
        FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER, "root": Role.ADMIN}
    ) as c:
        private = await create(c["alice"], "비공개", visibility="private")
        public = await create(c["alice"], "공개", visibility="public")
        # when: bob·alice·admin이 목록을 읽는다
        bob = [i["id"] for i in (await c["bob"].get(URL)).json()]
        alice = [i["id"] for i in (await c["alice"].get(URL)).json()]
        admin = [i["id"] for i in (await c["root"].get(URL)).json()]
    # then: bob에게는 공개만, alice·admin에게는 둘 다(같은 시각이면 id 내림차순)
    assert bob == [public["id"]]
    assert alice == [public["id"], private["id"]]
    assert admin == [public["id"], private["id"]]


async def test_get_returns_the_detail_of_a_visible_report() -> None:
    """볼 수 있는 리포트의 상세는 정의·SQL·revision·차트·배치를 담는다.

    테스트 코드: RS-013
    """
    # given: alice의 공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], "공개", visibility="public")
        # when: bob이 상세를 연다
        response = await c["bob"].get(f"{URL}/{made['id']}")
    # then: 200이고 만들 때의 상세와 같으며 상세 키를 모두 가진다
    assert response.status_code == 200, response.text
    assert response.json() == made
    assert {"revision", "definition", "generated_sql", "chart", "chart_problem", "layout"} <= set(
        response.json()
    )


async def test_get_of_a_hidden_report_equals_get_of_a_missing_one() -> None:
    """남의 비공개 리포트의 상세는 없는 id와 같은 404이고 문구가 같다.

    테스트 코드: RS-014
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        hidden = await create(c["alice"], "비공개", visibility="private")
        # when: bob이 비공개 리포트와 없는 id를 연다
        hidden_response = await c["bob"].get(f"{URL}/{hidden['id']}")
        missing_response = await c["bob"].get(f"{URL}/{MISSING_ID}")
    # then: 둘 다 404 not-found이고 문구가 같다
    hidden_body = problem(hidden_response, 404, "not-found")
    missing_body = problem(missing_response, 404, "not-found")
    assert hidden_body["detail"] == missing_body["detail"] == "리포트를 찾을 수 없습니다."


# ---- 수정 ----


async def test_put_updates_the_report_and_bumps_the_revision() -> None:
    """남의 공개 리포트를 덮어쓰면 revision이 오르고 만든 사람은 그대로, 최종 수정자는 요청자다.

    테스트 코드: RS-016, RS-017
    """
    # given: alice의 공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], "원본", visibility="public")
        # when: user bob이 revision 1로 덮어쓴다
        response = await c["bob"].put(
            f"{URL}/{made['id']}",
            json=update_body(1, "수정본", description="새 설명", visibility="public"),
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 이름·설명·revision 2가 바뀌고 만든 사람은 alice, 최종 수정자는 bob이며 다시 열어도 같다
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["description"], body["revision"]) == ("수정본", "새 설명", 2)
    assert body["owner"]["label"] == "사용자 alice"
    assert body["updated_by"]["label"] == "사용자 bob"
    assert reread.json() == body


async def test_put_with_a_stale_revision_is_409_invalid_state() -> None:
    """낡은 revision으로 덮어쓰면 409 invalid-state이고 먼저 저장한 값이 남는다.

    테스트 코드: RS-018
    """
    # given: 한 번 덮어써 revision 2가 된 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        first = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1, "첫째"))
        # when: 같은 revision 1로 다시 덮어쓴다
        stale = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1, "둘째"))
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 첫째는 200, 둘째는 409 invalid-state 문구이고 리포트는 첫째 값이다
    assert first.status_code == 200
    body = problem(stale, 409, "invalid-state")
    assert str(body["detail"]).startswith("다른 사용자가 먼저 이 리포트를 저장했습니다")
    assert reread.json()["name"] == "첫째"


async def test_put_by_a_non_owner_changing_visibility_is_403_forbidden() -> None:
    """만든 사람이 아닌 편집자가 공개 범위를 바꾸면 403 forbidden이다.

    테스트 코드: RS-019
    """
    # given: alice의 공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], visibility="public")
        # when: bob이 private으로 덮어쓴다
        response = await c["bob"].put(
            f"{URL}/{made['id']}", json=update_body(1, visibility="private")
        )
    # then: 403 forbidden 문구다
    body = problem(response, 403, "forbidden")
    assert body["detail"] == "공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다."


async def test_put_of_others_private_report_is_404_even_with_a_wrong_revision() -> None:
    """남의 비공개 리포트의 덮어쓰기는 revision이 틀려도 404다.

    테스트 코드: RS-014
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], visibility="private")
        # when: bob이 틀린 revision으로 덮어쓴다
        response = await c["bob"].put(f"{URL}/{made['id']}", json=update_body(99))
    # then: 404 not-found다
    problem(response, 404, "not-found")


async def test_renaming_to_a_name_the_owner_already_uses_is_409_already_exists() -> None:
    """다른 리포트의 이름으로 덮어쓰면 409 already-exists이다.

    테스트 코드: RS-022
    """
    # given: alice의 "기존"과 공개 "대상"
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        await create(c["alice"], "기존", visibility="public")
        target = await create(c["alice"], "대상", visibility="public")
        # when: bob이 "대상"을 "기존"으로 덮어쓴다
        response = await c["bob"].put(f"{URL}/{target['id']}", json=update_body(1, "기존"))
    # then: 409 already-exists 문구다
    body = problem(response, 409, "already-exists")
    assert body["detail"] == "같은 이름의 리포트가 이미 있습니다."


# ---- 삭제 ----


async def test_delete_removes_the_report() -> None:
    """만든 사람이 지우면 204이고 그 뒤 상세는 404다.

    테스트 코드: RS-024
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 지운다
        deleted = await c["alice"].delete(f"{URL}/{made['id']}")
        after = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 204이고 다시 열면 404다
    assert deleted.status_code == 204
    problem(after, 404, "not-found")


async def test_delete_of_others_public_report_is_403_and_admin_delete_is_204() -> None:
    """남의 공개 리포트의 삭제는 403이고 admin은 204다.

    테스트 코드: RS-025, RS-026
    """
    # given: alice의 공개 리포트
    async with clients(
        FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES, "root": Role.ADMIN}
    ) as c:
        made = await create(c["alice"], visibility="public")
        # when: bob이 지우고, 다시 열고, admin이 지운다
        denied = await c["bob"].delete(f"{URL}/{made['id']}")
        still = await c["bob"].get(f"{URL}/{made['id']}")
        allowed = await c["root"].delete(f"{URL}/{made['id']}")
    # then: bob은 403 forbidden 문구이고 리포트는 남아 있다가 admin 삭제는 204다
    body = problem(denied, 403, "forbidden")
    assert body["detail"] == "리포트를 만든 사람 또는 admin만 삭제할 수 있습니다."
    assert still.status_code == 200
    assert allowed.status_code == 204


async def test_delete_of_others_private_report_is_404() -> None:
    """남의 비공개 리포트의 삭제는 404다.

    테스트 코드: RS-014
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], visibility="private")
        # when: bob이 지운다
        response = await c["bob"].delete(f"{URL}/{made['id']}")
    # then: 404 not-found다
    problem(response, 404, "not-found")


# ---- 복제 ----


async def test_copy_returns_201_location_and_a_new_report_owned_by_the_requester() -> None:
    """복제하면 201과 Location이고 새 리포트는 원본 정의, 요청자 소유, revision 1이다.

    테스트 코드: RS-028
    """
    # given: alice의 공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        source = await create(c["alice"], "원본", visibility="public")
        # when: user bob이 메타를 정해 복제한다
        response = await c["bob"].post(
            f"{URL}/{source['id']}/copy",
            json={"name": "원본 복사본", "description": "복사", "visibility": "private"},
        )
    # then: 201과 Location, 새 id, 보낸 메타, 요청자 소유, revision 1, 원본 정의다
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
    assert body["layout"] == source["layout"]


async def test_copy_description_defaults_to_empty() -> None:
    """복제 요청의 설명을 생략하면 빈 문자열이다.

    테스트 코드: RS-029
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        source = await create(c["alice"], "원본")
        # when: 설명 없이 복제한다
        response = await c["alice"].post(
            f"{URL}/{source['id']}/copy", json={"name": "복사", "visibility": "public"}
        )
    # then: 201이고 설명은 빈 문자열이다
    assert response.status_code == 201, response.text
    assert response.json()["description"] == ""


async def test_copy_with_a_name_the_requester_already_uses_is_409() -> None:
    """이미 있는 이름으로 복제하면 409 already-exists이다.

    테스트 코드: RS-030
    """
    # given: alice의 "원본"
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        source = await create(c["alice"], "원본")
        # when: 같은 이름으로 복제한다
        response = await c["alice"].post(
            f"{URL}/{source['id']}/copy", json={"name": "원본", "visibility": "public"}
        )
    # then: 409 already-exists다
    problem(response, 409, "already-exists")


async def test_copy_of_a_hidden_report_is_404() -> None:
    """남의 비공개 리포트의 복제는 404다.

    테스트 코드: RS-014
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        source = await create(c["alice"], "비공개", visibility="private")
        # when: bob이 복제한다
        response = await c["bob"].post(
            f"{URL}/{source['id']}/copy", json={"name": "복사", "visibility": "public"}
        )
    # then: 404 not-found다
    problem(response, 404, "not-found")


# ---- 실행 ----


async def test_run_returns_the_query_response_shape() -> None:
    """저장 리포트 실행 응답은 같은 정의를 /query로 보낸 응답과 같다.

    테스트 코드: RS-032
    """
    # given: Fake 조회 응답과 user의 리포트
    use_cases = FakeUseCases()
    use_cases.uow.reports.respond_with([["20261016-0001"]], total_count=7, sql="SELECT demo")
    async with clients(use_cases, {"alice": Role.USER}) as c:
        made = await create(c["alice"])
        # when: 실행하고, 같은 정의를 /query로 조회한다
        run = await c["alice"].post(f"{URL}/{made['id']}/run")
        query = await c["alice"].post(f"{URL}/query", json=VALID_DEFINITION)
    # then: 두 응답이 같고 행·SQL이 Fake 응답이다
    assert run.status_code == 200, run.text
    assert run.json() == query.json()
    assert run.json()["rows"] == [["20261016-0001"]]
    assert run.json()["sql"] == "SELECT demo"


async def test_run_of_a_hidden_report_is_404() -> None:
    """남의 비공개 리포트의 실행은 404다.

    테스트 코드: RS-014
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        made = await create(c["alice"], visibility="private")
        # when: bob이 실행한다
        response = await c["bob"].post(f"{URL}/{made['id']}/run")
    # then: 404 not-found다
    problem(response, 404, "not-found")


async def test_run_timeout_is_503_report_timeout() -> None:
    """실행이 시간 초과되면 503 report-timeout이다.

    테스트 코드: RS-034
    """
    from app.application.ports.report_query_runner import ReportQueryTimeoutError  # noqa: PLC0415

    # given: 실행이 시간 초과되는 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        use_cases.uow.reports.error = ReportQueryTimeoutError()
        # when: 실행한다
        response = await c["alice"].post(f"{URL}/{made['id']}/run")
    # then: 503 report-timeout이다
    problem(response, 503, "report-timeout")


# ---- 라우트 순서와 경로 id ----


async def test_fields_route_still_wins_over_report_id() -> None:
    """/reports/fields는 리포트 id 경로에 걸리지 않고 카탈로그를 준다.

    테스트 코드: RS-051
    """
    # given: 로그인한 user
    async with clients(FakeUseCases(), {"alice": Role.USER}) as c:
        # when: /reports/fields를 부른다
        response = await c["alice"].get(f"{URL}/fields")
    # then: 카탈로그 응답이다(422·404가 아니다)
    assert response.status_code == 200, response.text
    assert [f["key"] for f in response.json()["fields"]] == [f.key for f in FIELD_CATALOG]


async def test_query_route_still_works_beside_the_saved_report_routes() -> None:
    """/reports/query는 리포트 id 경로에 걸리지 않고 조회 응답을 준다.

    테스트 코드: RS-051
    """
    # given: 로그인한 user
    async with clients(FakeUseCases(), {"alice": Role.USER}) as c:
        # when: /reports/query를 부른다
        response = await c["alice"].post(f"{URL}/query", json=VALID_DEFINITION)
    # then: 조회 응답이다
    assert response.status_code == 200, response.text
    assert "rows" in response.json()


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", str(2**53)])
async def test_malformed_report_ids_are_request_validation(bad_id: str) -> None:
    """잘못된 리포트 id 경로는 422 request-validation이다.

    테스트 코드: RS-050
    """
    # given: 로그인한 sales
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 잘못된 id로 상세를 연다
        response = await c["alice"].get(f"{URL}/{bad_id}")
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


# ---- 로그인·CSRF ----


async def test_every_saved_report_route_requires_login() -> None:
    """로그인하지 않으면 저장 리포트 경로 7개 모두 401이다.

    테스트 코드: RS-050
    """
    # given: 로그인하지 않은 클라이언트
    async with clients(FakeUseCases(), {"anon": Role.USER}) as c:
        # when: 저장 리포트 경로를 모두 부른다
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
    # then: 모두 401 unauthenticated다
    for response in calls:
        problem(response, 401, "unauthenticated")


async def test_writes_without_the_csrf_header_are_403_csrf() -> None:
    """상태 변경 요청에 CSRF 헤더가 없으면 403 csrf이다.

    테스트 코드: RS-050
    """
    # given: 로그인했지만 CSRF 헤더를 보내지 않는 클라이언트
    async with clients(FakeUseCases(), {"alice": Role.SALES}, csrf=False) as c:
        # when: 만들기와 삭제를 부른다
        created = await c["alice"].post(URL, json=create_body())
        deleted = await c["alice"].delete(f"{URL}/{MISSING_ID}")
    # then: 둘 다 403 csrf다
    problem(created, 403, "csrf")
    problem(deleted, 403, "csrf")


# ---- 이름은 모든 리포트 사이에서 고유 ----


async def test_create_with_a_name_of_another_users_private_report_is_409() -> None:
    """남의 비공개 리포트와 대소문자만 다른 이름으로 만들면 409 already-exists이다.

    테스트 코드: RS-008
    """
    # given: alice의 비공개 "Sales"
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        await create(c["alice"], "Sales", visibility="private")
        # when: bob이 "sales"로 만든다
        response = await c["bob"].post(URL, json=create_body("sales"))
    # then: 409 already-exists 문구다
    body = problem(response, 409, "already-exists")
    assert body["detail"] == "같은 이름의 리포트가 이미 있습니다."


async def test_copy_with_a_name_of_another_users_report_is_409() -> None:
    """남의 비공개 리포트 이름으로 복제하면 409 already-exists이다.

    테스트 코드: RS-030
    """
    # given: alice의 공개 "원본"과 비공개 "남의 이름"
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        source = await create(c["alice"], "원본", visibility="public")
        await create(c["alice"], "남의 이름", visibility="private")
        # when: bob이 "남의 이름"으로 복제한다
        response = await c["bob"].post(
            f"{URL}/{source['id']}/copy", json={"name": "남의 이름", "visibility": "public"}
        )
    # then: 409 already-exists다
    problem(response, 409, "already-exists")


# ---- 깨진 저장 정의 ----


async def _broken(use_cases: FakeUseCases, owner: str, **overrides: str) -> int:
    report = make_broken_report(owner=await use_cases.user_id_of(owner), **overrides)
    async with use_cases.uow as uow:
        await uow.saved_reports.add(report)
        await uow.commit()
    return int(report.id)


async def test_list_succeeds_with_a_broken_report_and_shows_empty_entities() -> None:
    """깨진 저장 정의 리포트가 있어도 목록은 200이고 그 항목의 데이터는 비어 있다.

    테스트 코드: RS-035
    """
    # given: alice의 깨진 리포트와 정상 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice", name="깨짐")
        await create(c["alice"], "정상")
        # when: 목록을 읽는다
        response = await c["alice"].get(URL)
    # then: 200이고 깨진 항목의 entities는 [], 정상은 ["deal"]이다
    assert response.status_code == 200, response.text
    by_name = {item["name"]: item for item in response.json()}
    assert by_name["깨짐"]["id"] == broken_id
    assert by_name["깨짐"]["entities"] == []
    assert by_name["정상"]["entities"] == ["deal"]


async def test_others_private_broken_report_is_404_on_get() -> None:
    """남의 비공개 깨진 리포트는 목록에서 숨고 상세는 stored-invalid가 아니라 404다.

    테스트 코드: RS-035, RS-036
    """
    # given: bob의 비공개 깨진 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "bob", visibility="private")
        # when: alice가 목록을 읽고 상세를 연다
        listed = await c["alice"].get(URL)
        response = await c["alice"].get(f"{URL}/{broken_id}")
    # then: 목록은 비어 있고 상세는 404다
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
    """깨진 저장 정의의 상세·실행·복제는 422 invalid-report(stored-invalid)다.

    테스트 코드: RS-036
    """
    # given: alice의 깨진 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice")
        # when: 상세·실행·복제 중 하나를 부른다
        response = await c["alice"].request(method, f"{URL}/{broken_id}{suffix}", json=body)
    # then: 422 invalid-report이고 errors는 (["definition"], "stored-invalid") 하나다
    problem_body = problem(response, 422, "invalid-report")
    assert [(e["location"], e["code"]) for e in problem_body["errors"]] == [
        (["definition"], "stored-invalid")
    ]


async def test_put_with_a_new_definition_repairs_a_broken_report() -> None:
    """깨진 저장 정의 리포트는 새 정의로 덮어써 복구되고 그 뒤 상세가 열린다.

    테스트 코드: RS-037
    """
    # given: alice의 깨진 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice")
        # when: 새 정의로 덮어쓰고 다시 연다
        updated = await c["alice"].put(f"{URL}/{broken_id}", json=update_body(1, "복구됨"))
        reread = await c["alice"].get(f"{URL}/{broken_id}")
    # then: 둘 다 200이고 정의를 읽을 수 있으며 revision 2다
    assert updated.status_code == 200, updated.text
    assert reread.status_code == 200, reread.text
    assert reread.json()["definition"]["columns"][0]["field"] == "deal.code"
    assert reread.json()["revision"] == 2


async def test_delete_removes_a_broken_report() -> None:
    """깨진 저장 정의 리포트도 지울 수 있다.

    테스트 코드: RS-037
    """
    # given: alice의 깨진 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _broken(use_cases, "alice")
        # when: 지운다
        deleted = await c["alice"].delete(f"{URL}/{broken_id}")
        listed = await c["alice"].get(URL)
    # then: 204이고 목록에서 사라진다
    assert deleted.status_code == 204
    assert listed.json() == []


# ---- 예전 포맷 요청은 거절 ----


@pytest.mark.parametrize(
    ("field", "legacy"),
    [("deal.name", x) for x in ["as_is", "prefix", "name", "key"]]
    + [
        ("deal.amount", x)
        for x in ["thousands", "krw_thousand", "krw_million", "decimal1", "percent_share"]
    ],
)
async def test_create_and_update_with_legacy_format_are_rejected(field: str, legacy: str) -> None:
    """예전 텍스트·숫자 포맷으로 저장하거나 덮어쓰면 422 invalid-report다."""
    # given: 예전 포맷을 쓴 정의와 이미 저장된 리포트
    definition = {"columns": [{"field": field, "format": legacy}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 그 정의로 새로 저장하고, 그 정의로 덮어쓴다
        created = await c["alice"].post(URL, json=create_body("새것", definition=definition))
        updated = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, definition=definition)
        )

    # then: 둘 다 format-not-allowed 위반 하나의 422 invalid-report다
    for response in (created, updated):
        body = problem(response, 422, "invalid-report")
        assert [(e["location"], e["code"]) for e in body["errors"]] == [
            (["columns", 0, "format"], "format-not-allowed")
        ]


async def test_created_report_is_opened_with_the_same_server_rendered_sql_and_conditions() -> None:
    """저장한 리포트를 다시 열어도 서버가 만든 SQL과 보낸 조건이 같다.

    테스트 코드: RS-002
    """
    # given: 조건이 하나 있는 정의로 저장한 alice의 리포트
    definition = {
        "columns": [{"field": "deal.code"}],
        "conditions": [{"field": "deal.name", "operator": "contains", "value": "a"}],
    }
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=definition)
        # when: 상세로 다시 연다
        opened = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 서버가 만든 SELECT SQL이 저장 응답과 같고 조건이 보낸 그대로다
    assert opened.json()["generated_sql"] == made["generated_sql"] == RENDERED_SQL
    assert RENDERED_SQL.startswith("SELECT")
    (condition,) = opened.json()["definition"]["conditions"]
    assert (condition["field"], condition["operator"], condition["value"]) == (
        "deal.name",
        "contains",
        "a",
    )
