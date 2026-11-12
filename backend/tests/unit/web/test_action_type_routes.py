"""Action 유형 라우터: FakeUseCases 위의 HTTP 계약, 문구, 상태 코드.

DB 없이 라우터·스키마·오류 매핑을 확인하는 단위 테스트다.
권한은 test_action_type_route_permissions.py.
"""

import pytest

from app.domain.auth.principal import Role
from tests.support.ids import MISSING_ID
from tests.unit.web.action_type_http import (
    DEFAULT_NAMES,
    TYPE_KEYS,
    URL,
    seeded_use_cases,
    type_id_of,
    use_type,
)
from tests.unit.web.vendor_http import client_for, problem

# ---- 조회 ----


async def test_list_returns_the_defaults_in_order_with_the_documented_keys() -> None:
    """유형 목록은 기본 8개를 시드 순서로, 문서의 키와 함께, 만든 사람 없이 돌려준다.

    테스트 코드: CL-025
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 유형 목록을 부른다
        response = await http.get(URL)

    # then: 200, 시드 순서 8개, 키가 정확하고 모두 기본·만든 사람 없음·사용 0이다
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["name"] for item in body] == DEFAULT_NAMES
    assert all(set(item) == TYPE_KEYS for item in body)
    assert all(item["is_default"] is True for item in body)
    assert all(item["created_by"] is None for item in body)
    assert all(item["usage_count"] == 0 for item in body)


async def test_action_type_ids_are_json_integers() -> None:
    """유형 id와 만든 사람 id는 JSON 정수다.

    테스트 코드: CL-025
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 유형을 만들고 목록을 읽는다
        created = (await http.post(URL, json={"name": "웨비나"})).json()
        listed = (await http.get(URL)).json()

    # then: id가 모두 정수다
    assert type(created["id"]) is int
    assert type(created["created_by"]["id"]) is int
    assert all(type(item["id"]) is int for item in listed)


async def test_custom_types_follow_the_defaults_in_lower_name_order() -> None:
    """직접 만든 유형은 기본 유형 뒤에 소문자 이름 코드 포인트 순으로 나온다.

    테스트 코드: CL-026
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 'Zeta', 'alpha', '나중'을 만들고 목록을 읽는다
        for name in ("Zeta", "alpha", "나중"):
            assert (await http.post(URL, json={"name": name})).status_code == 201
        body = (await http.get(URL)).json()

    # then: 기본 8개 뒤에 alpha, Zeta, 나중 순이다
    assert [item["name"] for item in body] == [*DEFAULT_NAMES, "alpha", "Zeta", "나중"]


async def test_list_reports_how_many_actions_use_each_type() -> None:
    """유형의 사용 수는 그 유형을 쓰는 Action 수다.

    테스트 코드: CL-027
    """
    # given: '미팅' Action 3건, '데모' Action 1건
    use_cases = seeded_use_cases()
    await use_type(use_cases, "미팅", count=3)
    await use_type(use_cases, "데모", count=1)
    async with client_for(use_cases) as http:
        # when: 유형 목록을 읽는다
        body = (await http.get(URL)).json()

    # then: '미팅' 3, '데모' 1, '통화' 0이다
    usage = {item["name"]: item["usage_count"] for item in body}
    assert (usage["미팅"], usage["데모"], usage["통화"]) == (3, 1, 0)


# ---- 생성 ----


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_create_returns_201_with_location_and_the_creator(role: Role) -> None:
    """sales·admin이 유형을 만들면 201·Location이고 정규화된 이름·만든 사람이 실린다.

    테스트 코드: CL-028
    """
    # given: sales 또는 admin으로 로그인
    async with client_for(seeded_use_cases(), role=role) as http:
        # when: '  웨비나  '를 만든다
        response = await http.post(URL, json={"name": "  웨비나  "})

    # then: 201, Location, 정규화된 이름, 기본 아님, 사용 0, 만든 사람이 있다
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == TYPE_KEYS
    assert (body["name"], body["is_default"], body["usage_count"]) == ("웨비나", False, 0)
    assert body["created_by"] is not None
    assert response.headers["location"] == f"{URL}/{body['id']}"


async def test_the_created_type_is_listed_afterwards() -> None:
    """만든 유형은 목록에 나온다.

    테스트 코드: CL-028
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: '웨비나'를 만들고 목록을 읽는다
        created = (await http.post(URL, json={"name": "웨비나"})).json()
        listed = (await http.get(URL)).json()

    # then: 만든 유형의 id가 목록에 있다
    assert created["id"] in [item["id"] for item in listed]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("   ", "유형을 입력하세요."),
        ("", "유형을 입력하세요."),
        ("가" * 51, "유형은 50자 이내로 입력하세요."),
    ],
)
async def test_invalid_names_are_422_with_the_domain_message(name: str, message: str) -> None:
    """공백·빈 이름은 필수 문구, 51자는 길이 문구로 422다.

    테스트 코드: CL-031
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 유효하지 않은 이름으로 만든다
        response = await http.post(URL, json={"name": name})

    # then: 422 invalid-value와 해당 문구다
    assert problem(response, 422, "invalid-value")["detail"] == message


async def test_a_50_character_name_is_accepted() -> None:
    """유형 이름은 50자까지 만들어진다.

    테스트 코드: CL-031
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 50자 이름으로 만든다
        response = await http.post(URL, json={"name": "가" * 50})

    # then: 201이다
    assert response.status_code == 201, response.text


async def test_a_nul_in_the_name_is_422() -> None:
    """NUL 문자가 든 유형 이름은 422이고 저장되지 않는다.

    테스트 코드: CL-032
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: NUL이 든 이름으로 만든다
        response = await http.post(URL, json={"name": "웨\u0000비나"})
        listed = (await http.get(URL)).json()

    # then: 422 invalid-value NUL 문구이고 유형은 8개다
    assert problem(response, 422, "invalid-value")["detail"] == "유형에는 NUL 문자를 쓸 수 없습니다"
    assert len(listed) == len(DEFAULT_NAMES)


@pytest.mark.parametrize("body", [{}, {"name": 1}, {"name": "웨비나", "extra": 1}])
async def test_a_malformed_body_is_request_validation(body: dict[str, object]) -> None:
    """이름 누락·정수 이름·모르는 필드는 422 request-validation이다.

    테스트 코드: CL-033
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 형식이 틀린 본문으로 만든다
        response = await http.post(URL, json=body)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("name", ["demo", "DEMO", " Demo "])
async def test_a_duplicate_name_ignoring_case_is_409(name: str) -> None:
    """이미 있는 유형과 대소문자·공백만 다른 이름은 409다.

    테스트 코드: CL-030
    """
    # given: 'Demo' 유형을 만들었다
    async with client_for(seeded_use_cases()) as http:
        assert (await http.post(URL, json={"name": "Demo"})).status_code == 201
        # when: 대소문자·공백만 다른 이름으로 만든다
        response = await http.post(URL, json={"name": name})

    # then: 409 already-exists 문구다
    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 유형 이름입니다."


async def test_the_name_of_a_seeded_default_is_taken() -> None:
    """기본 유형의 이름과 같은 이름은 409다.

    테스트 코드: CL-030
    """
    # given: 기본 유형 '미팅'이 있다
    async with client_for(seeded_use_cases()) as http:
        # when: '미팅'을 만든다
        response = await http.post(URL, json={"name": "미팅"})

    # then: 409 already-exists 문구다
    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 유형 이름입니다."


# ---- 이름 변경 ----


async def test_rename_returns_the_renamed_default_type() -> None:
    """admin이 기본 유형 이름을 바꾸면 자리·기본 표시가 유지된다.

    테스트 코드: CL-034
    """
    # given: 기본 유형 '미팅'(2번째)
    async with client_for(seeded_use_cases()) as http:
        meeting = await type_id_of(http, "미팅")
        # when: '  회의  '로 바꾼다
        response = await http.patch(f"{URL}/{meeting}", json={"name": "  회의  "})
        listed = (await http.get(URL)).json()

    # then: 200, 같은 id, 새 이름, 기본 표시 유지, 목록의 2번째 자리다
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["name"], body["is_default"]) == (meeting, "회의", True)
    assert set(body) == TYPE_KEYS
    assert [item["name"] for item in listed][1] == "회의"  # 기본 순서(2번째)는 그대로


async def test_rename_reports_the_usage_count() -> None:
    """이름 변경 응답에 사용 수가 함께 온다.

    테스트 코드: CL-034
    """
    # given: '미팅' Action 2건
    use_cases = seeded_use_cases()
    await use_type(use_cases, "미팅", count=2)
    async with client_for(use_cases) as http:
        meeting = await type_id_of(http, "미팅")
        # when: '미팅'을 '회의'로 바꾼다
        response = await http.patch(f"{URL}/{meeting}", json={"name": "회의"})

    # then: 사용 수가 2다
    assert response.json()["usage_count"] == 2


async def test_renaming_only_the_case_of_its_own_name_is_allowed() -> None:
    """유형 자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CL-035
    """
    # given: 'Webinar' 유형을 만들었다
    async with client_for(seeded_use_cases()) as http:
        created = (await http.post(URL, json={"name": "Webinar"})).json()
        # when: 'WEBINAR'로 바꾼다
        response = await http.patch(f"{URL}/{created['id']}", json={"name": "WEBINAR"})

    # then: 200이고 이름은 'WEBINAR'다
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "WEBINAR"


async def test_rename_to_another_types_name_ignoring_case_is_409() -> None:
    """다른 유형의 이름으로 바꾸면 409이다.

    테스트 코드: CL-036
    """
    # given: 'Webinar' 유형을 만들었다
    async with client_for(seeded_use_cases()) as http:
        demo = await type_id_of(http, "데모")
        await http.post(URL, json={"name": "Webinar"})
        # when: '데모'를 'webinar'로 바꾼다
        response = await http.patch(f"{URL}/{demo}", json={"name": "webinar"})

    # then: 409 already-exists 문구다
    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 유형 이름입니다."


async def test_rename_with_a_blank_name_is_422_and_with_an_unknown_id_is_404() -> None:
    """공백뿐인 새 이름은 422, 없는 id의 이름 변경은 404다.

    테스트 코드: CL-037, CL-038
    """
    # given: 기본 유형 '데모'가 있다
    async with client_for(seeded_use_cases()) as http:
        demo = await type_id_of(http, "데모")
        # when: '데모'를 공백으로, 없는 id를 '무엇'으로 바꾼다
        blank = await http.patch(f"{URL}/{demo}", json={"name": " "})
        missing = await http.patch(f"{URL}/{MISSING_ID}", json={"name": "무엇"})

    # then: 422 필수 문구와 404 not-found다
    assert problem(blank, 422, "invalid-value")["detail"] == "유형을 입력하세요."
    problem(missing, 404, "not-found")


# ---- 삭제 ----


async def test_delete_an_unused_type_is_204_and_the_type_disappears() -> None:
    """쓰이지 않는 유형은 삭제되고 목록에서 사라진다.

    테스트 코드: CL-040
    """
    # given: '데모'는 쓰이지 않는다
    async with client_for(seeded_use_cases()) as http:
        demo = await type_id_of(http, "데모")
        # when: '데모'를 삭제한다
        response = await http.delete(f"{URL}/{demo}")
        listed = (await http.get(URL)).json()

    # then: 204이고 목록에서 '데모'가 없다
    assert response.status_code == 204
    assert "데모" not in [item["name"] for item in listed]


async def test_delete_a_used_type_is_409_with_the_count_and_keeps_the_type() -> None:
    """Action이 쓰는 유형을 지우면 409(실제 Action 수)이고 유형은 남는다.

    테스트 코드: CL-041
    """
    # given: '미팅' Action 2건
    use_cases = seeded_use_cases()
    await use_type(use_cases, "미팅", count=2)
    async with client_for(use_cases) as http:
        meeting = await type_id_of(http, "미팅")
        # when: '미팅'을 삭제한다
        response = await http.delete(f"{URL}/{meeting}")
        listed = (await http.get(URL)).json()

    # then: 409 invalid-state '(Action 2건)'이고 '미팅'이 남는다
    detail = "사용 중인 유형은 삭제할 수 없습니다. (Action 2건)"
    assert problem(response, 409, "invalid-state")["detail"] == detail
    assert "미팅" in [item["name"] for item in listed]


async def test_delete_an_unknown_id_is_404() -> None:
    """없는 유형을 삭제하면 404다.

    테스트 코드: CL-038
    """
    # given: 기본 유형 8개가 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 없는 id를 삭제한다
        response = await http.delete(f"{URL}/{MISSING_ID}")

    # then: 404 not-found다
    problem(response, 404, "not-found")


async def test_a_malformed_id_in_the_path_is_request_validation() -> None:
    """경로의 유형 id 형식이 틀리면 422 request-validation이다."""
    # given: 기본 유형이 시드된 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 정수가 아닌 id로 이름 변경·삭제를 부른다
        patched = await http.patch(f"{URL}/not-an-id", json={"name": "x"})
        deleted = await http.delete(f"{URL}/not-an-id")

    # then: 둘 다 422 request-validation이다
    problem(patched, 422, "request-validation")
    problem(deleted, 422, "request-validation")
