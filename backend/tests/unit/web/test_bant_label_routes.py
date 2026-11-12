"""BANT Label 라우터: FakeUseCases 위의 HTTP 계약, 문구, 상태 코드.

DB 없이 라우터·스키마·오류 매핑을 확인하는 단위 테스트다. 권한 판정은
test_bant_label_route_permissions.py가 맡는다.
"""

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.support.ids import MISSING_ID
from tests.unit.web.bant_label_http import (
    BASELINE,
    CATEGORIES,
    DEFAULT_COUNTS,
    LABEL_KEYS,
    URL,
    label_id_of,
    labels_of,
    seeded_use_cases,
    use_label,
)
from tests.unit.web.vendor_http import client_for, problem

REQUIRED = "Label 이름을 입력하세요."
TOO_LONG = "Label 이름은 50자 이내로 입력하세요."
NUL = "Label 이름에는 NUL 문자를 쓸 수 없습니다"
DUPLICATE = "같은 구분에 이미 있는 Label 이름입니다."
IN_USE = "사용 중인 Label은 삭제할 수 없습니다. (Deal {count}건)"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_lists_the_23_defaults_in_seed_order_with_the_documented_keys(
    role: Role,
) -> None:
    """모든 역할이 Label 목록을 보면 기본 23개가 구분·시드 순서로 문서의 필드와 함께 나온다.

    테스트 코드: CL-001
    """
    # given: 기본 시드 상태
    use_cases = seeded_use_cases()

    # when: 해당 역할이 Label 목록을 부른다
    async with client_for(use_cases, role=role) as http:
        body = await labels_of(http)

    # then: 7·6·5·5개가 시드 순서이고 키가 정확하며 모두 기본·만든 사람 없음·사용 0이다
    assert len(body) == BASELINE
    assert [(x["category"], x["name"]) for x in body] == [
        (category, name) for category in CATEGORIES for name in DEFAULT_LABELS[category]
    ]
    assert [sum(1 for x in body if x["category"] == c) for c in CATEGORIES] == [
        DEFAULT_COUNTS[c] for c in CATEGORIES
    ]
    assert all(set(x) == LABEL_KEYS for x in body)
    assert all(x["is_default"] is True and x["created_by"] is None for x in body)
    assert all(x["usage_count"] == 0 for x in body)
    assert all(type(x["id"]) is int for x in body)


async def test_custom_labels_follow_the_defaults_of_their_category_in_lower_name_order() -> None:
    """직접 만든 Label은 그 구분의 기본 Label 뒤에 소문자 이름 코드 포인트 순으로 나온다.

    테스트 코드: CL-002
    """
    # given: need 구분에 '나중에', 'Zeta', 'alpha'를 이 순서로 만들었다
    async with client_for(seeded_use_cases(), role=Role.SALES) as http:
        for name in ("나중에", "Zeta", "alpha"):
            assert (
                await http.post(URL, json={"category": "need", "name": name})
            ).status_code == 201

        # when: 목록을 읽는다
        body = await labels_of(http)

    # then: need는 기본 5개 뒤에 alpha, Zeta, 나중에 순이고 다른 구분은 기본 그대로다
    need = [x["name"] for x in body if x["category"] == "need"]
    assert need == [*DEFAULT_LABELS["need"], "alpha", "Zeta", "나중에"]
    assert len(body) == BASELINE + 3


async def test_usage_count_is_the_number_of_deals_that_selected_the_label() -> None:
    """Label의 사용 수는 그 Label을 선택한 Deal 수이고 안 쓰면 0이다.

    테스트 코드: CL-003
    """
    # given: '풀 예산 확보'를 Deal 2건이, 'CISO 지시'를 Deal 1건이 선택했다
    use_cases = seeded_use_cases()
    async with client_for(use_cases) as http:
        budget = await label_id_of(http, "budget", "풀 예산 확보")
        need = await label_id_of(http, "need", "CISO 지시")
    await use_label(use_cases, budget, "budget", count=2)
    await use_label(use_cases, need, "need", count=1, start=3)

    # when: 목록을 읽는다
    async with client_for(use_cases) as http:
        body = await labels_of(http)

    # then: 두 Label만 2, 1이고 나머지는 0이다
    usage = {x["name"]: x["usage_count"] for x in body if x["usage_count"]}
    assert usage == {"풀 예산 확보": 2, "CISO 지시": 1}


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_create_returns_201_with_location_the_trimmed_name_and_the_creator(
    role: Role,
) -> None:
    """sales·admin이 Label을 만들면 201·Location이고 이름은 정규화되며 만든 사람이 기록된다.

    테스트 코드: CL-004
    """
    # given: sales 또는 admin으로 로그인
    use_cases = seeded_use_cases()

    # when: need에 '  규제 대응  '을 만든다
    async with client_for(use_cases, role=role) as http:
        response = await http.post(URL, json={"category": "need", "name": "  규제 대응  "})

    # then: 201, Location, 정규화된 이름, 기본 아님, 사용 0, 만든 사람은 요청자다
    assert response.status_code == 201, response.text
    body = response.json()
    login_id = "root" if role is Role.ADMIN else f"{role.value}-user"
    creator = await use_cases.uow.users.get_active_by_login_id(LoginId(login_id))
    assert creator is not None
    assert set(body) == LABEL_KEYS
    assert (body["category"], body["name"]) == ("need", "규제 대응")
    assert (body["is_default"], body["usage_count"]) == (False, 0)
    assert body["created_by"]["id"] == creator.id
    assert body["created_at"] == body["updated_at"]
    assert response.headers["location"] == f"{URL}/{body['id']}"
    assert type(body["id"]) is int


@pytest.mark.parametrize("name", ["ceo 보고 완료", "CEO 보고 완료", " Ceo 보고 완료 "])
async def test_a_name_that_differs_only_in_case_or_spaces_in_the_category_is_409(
    name: str,
) -> None:
    """같은 구분에 대소문자·공백만 다른 Label 이름은 409다.

    테스트 코드: CL-006
    """
    # given: authority에 'CEO 보고 완료'가 있다
    async with client_for(seeded_use_cases()) as http:
        # when: 대소문자·공백만 다른 이름으로 authority에 만든다
        response = await http.post(URL, json={"category": "authority", "name": name})
        count = len(await labels_of(http))

    # then: 409 already-exists 문구이고 Label은 23개 그대로다
    assert problem(response, 409, "already-exists")["detail"] == DUPLICATE
    assert count == BASELINE


async def test_the_same_name_may_be_created_in_another_category() -> None:
    """다른 구분에 있는 이름으로는 Label을 만들 수 있다.

    테스트 코드: CL-007
    """
    # given: '모름'은 authority·need에만 있다
    async with client_for(seeded_use_cases()) as http:
        # when: budget에 '모름'을 만든다
        response = await http.post(URL, json={"category": "budget", "name": "모름"})
        budget = [x["name"] for x in await labels_of(http) if x["category"] == "budget"]

    # then: 201이고 budget은 기본 7개 뒤에 '모름'이 있다
    assert response.status_code == 201, response.text
    assert budget == [*DEFAULT_LABELS["budget"], "모름"]


@pytest.mark.parametrize("name", ["", "   "], ids=["empty", "blank"])
async def test_a_blank_name_is_422_and_nothing_is_saved(name: str) -> None:
    """비었거나 공백뿐인 Label 이름은 422이고 저장되지 않는다.

    테스트 코드: CL-008
    """
    # given: 기본 시드 상태
    async with client_for(seeded_use_cases()) as http:
        # when: need에 빈 이름이나 공백뿐인 이름으로 만든다
        response = await http.post(URL, json={"category": "need", "name": name})
        count = len(await labels_of(http))

    # then: 422 invalid-value 필수 문구이고 Label은 23개 그대로다
    assert problem(response, 422, "invalid-value")["detail"] == REQUIRED
    assert count == BASELINE


async def test_the_name_limit_is_50_code_points() -> None:
    """Label 이름은 50자(코드 포인트)까지 되고 51자는 422다.

    테스트 코드: CL-009
    """
    async with client_for(seeded_use_cases()) as http:
        # when: need에 이모지 50개로 만들고, 다시 51개로 만든다
        accepted = await http.post(URL, json={"category": "need", "name": "😀" * 50})
        refused = await http.post(URL, json={"category": "need", "name": "😀" * 51})
        names = [x["name"] for x in await labels_of(http) if x["category"] == "need"]

    # then: 첫 요청은 201이고 이름 그대로, 둘째는 422 길이 문구이며 저장되지 않는다
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["name"] == "😀" * 50
    assert problem(refused, 422, "invalid-value")["detail"] == TOO_LONG
    assert names == [*DEFAULT_LABELS["need"], "😀" * 50]


@pytest.mark.parametrize(
    "name", ["a\u0000b", "\u0000", "name\u0000"], ids=["inside", "only", "end"]
)
async def test_a_nul_in_the_name_is_422_on_create_and_on_rename(name: str) -> None:
    """NUL 문자가 든 Label 이름은 등록·이름 변경 모두 422이고 바뀌지 않는다.

    테스트 코드: CL-010
    """
    # given: budget의 첫 기본 Label '단독 예산 확보'
    async with client_for(seeded_use_cases()) as http:
        first = await label_id_of(http, "budget", "단독 예산 확보")

        # when: NUL이 든 이름으로 need에 만들고, 같은 이름으로 '단독 예산 확보'를 바꾼다
        created = await http.post(URL, json={"category": "need", "name": name})
        renamed = await http.patch(f"{URL}/{first}", json={"name": name})
        body = await labels_of(http)

    # then: 둘 다 422 NUL 문구이고 Label은 23개, budget 이름은 그대로다
    assert problem(created, 422, "invalid-value")["detail"] == NUL
    assert problem(renamed, 422, "invalid-value")["detail"] == NUL
    assert len(body) == BASELINE
    assert body[0]["name"] == "단독 예산 확보"


@pytest.mark.parametrize(
    "payload",
    [
        {"category": "money", "name": "x"},
        {"category": "need"},
        {"category": "need", "name": "x", "score": 1},
    ],
    ids=["unknown-category", "missing-name", "unknown-field"],
)
async def test_a_malformed_create_body_is_request_validation(payload: dict[str, object]) -> None:
    """모르는 구분·이름 누락·모르는 필드로 Label을 만들면 422 request-validation이다.

    테스트 코드: CL-011
    """
    # given: 기본 시드 상태
    async with client_for(seeded_use_cases()) as http:
        # when: 형식이 틀린 본문으로 만든다
        response = await http.post(URL, json=payload)
        count = len(await labels_of(http))

    # then: 422 request-validation이고 Label은 23개 그대로다
    problem(response, 422, "request-validation")
    assert count == BASELINE


async def test_rename_of_a_default_label_keeps_the_id_category_default_flag_and_position() -> None:
    """admin이 기본 Label 이름을 바꾸면 같은 id·구분·기본 표시·자리가 유지된다.

    테스트 코드: CL-012
    """
    # given: ROOT로 로그인, budget '예산 없음'의 id
    async with client_for(seeded_use_cases()) as http:
        label_id = await label_id_of(http, "budget", "예산 없음")
        before = [x["name"] for x in await labels_of(http) if x["category"] == "budget"]

        # when: '  예산 미확보  '로 이름을 바꾼다
        response = await http.patch(f"{URL}/{label_id}", json={"name": "  예산 미확보  "})
        after = [x["name"] for x in await labels_of(http) if x["category"] == "budget"]

    # then: 200, 같은 id·구분, 정규화된 이름, 기본 표시 유지, 목록의 같은 자리다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == LABEL_KEYS
    assert (body["id"], body["category"], body["name"]) == (label_id, "budget", "예산 미확보")
    assert body["is_default"] is True
    assert after == ["예산 미확보" if name == "예산 없음" else name for name in before]


async def test_rename_of_someone_elses_label_keeps_the_creator_and_reports_usage() -> None:
    """다른 사람이 만든 Label 이름을 바꿔도 만든 사람은 그대로이고 응답에 사용 수가 있다.

    테스트 코드: CL-013
    """
    # given: KIM(sales)이 need '규제 대응'을 만들었고 Deal 1건이 그것을 선택했다
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.SALES) as kim:
        created = (await kim.post(URL, json={"category": "need", "name": "규제 대응"})).json()
    await use_label(use_cases, created["id"], "need")

    # when: ROOT가 '컴플라이언스 대응'으로 바꾼다
    async with client_for(use_cases) as root:
        response = await root.patch(f"{URL}/{created['id']}", json={"name": "컴플라이언스 대응"})

    # then: 200, 새 이름, 기본 아님, 만든 사람은 KIM 그대로, 사용 수 1이다
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["is_default"], body["usage_count"]) == (
        "컴플라이언스 대응",
        False,
        1,
    )
    assert body["created_by"] == created["created_by"]


async def test_renaming_only_the_case_of_its_own_name_is_allowed() -> None:
    """Label 자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CL-014
    """
    # given: authority 'CEO 보고 완료'
    async with client_for(seeded_use_cases()) as http:
        label_id = await label_id_of(http, "authority", "CEO 보고 완료")

        # when: 'ceo 보고 완료'로 바꾼다
        response = await http.patch(f"{URL}/{label_id}", json={"name": "ceo 보고 완료"})

    # then: 200이고 이름은 'ceo 보고 완료'다
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "ceo 보고 완료"


async def test_rename_to_another_labels_name_in_the_category_is_409_and_keeps_the_name() -> None:
    """같은 구분 다른 Label의 이름으로 바꾸면 409이고 이름은 그대로다.

    테스트 코드: CL-015
    """
    # given: authority 'CISO 보고 완료'와 'CEO 보고 완료'
    async with client_for(seeded_use_cases()) as http:
        label_id = await label_id_of(http, "authority", "CISO 보고 완료")

        # when: 'CISO 보고 완료'를 'ceo 보고 완료'로 바꾼다
        response = await http.patch(f"{URL}/{label_id}", json={"name": "ceo 보고 완료"})
        names = [x["name"] for x in await labels_of(http) if x["category"] == "authority"]

    # then: 409 already-exists 문구이고 'CISO 보고 완료'가 그대로 있다
    assert problem(response, 409, "already-exists")["detail"] == DUPLICATE
    assert "CISO 보고 완료" in names


async def test_rename_to_a_name_that_exists_only_in_another_category_is_allowed() -> None:
    """다른 구분에만 있는 이름으로는 Label 이름을 바꿀 수 있다.

    테스트 코드: CL-016
    """
    # given: budget '미확인'(authority·need에만 '모름'이 있다)
    async with client_for(seeded_use_cases()) as http:
        label_id = await label_id_of(http, "budget", "미확인")

        # when: '모름'으로 바꾼다
        response = await http.patch(f"{URL}/{label_id}", json={"name": "모름"})

    # then: 200, 구분은 budget, 이름은 '모름'이다
    assert response.status_code == 200, response.text
    assert (response.json()["category"], response.json()["name"]) == ("budget", "모름")


async def test_an_invalid_new_name_is_422_and_beats_a_missing_id() -> None:
    """잘못된 이름으로 Label 이름을 바꾸면 422이고 없는 id여도 이름 오류가 먼저다.

    테스트 코드: CL-017
    """
    async with client_for(seeded_use_cases()) as http:
        label_id = await label_id_of(http, "budget", "예산 없음")

        # when: '예산 없음'을 공백과 51자로, 없는 id를 공백으로 바꾼다
        blank = await http.patch(f"{URL}/{label_id}", json={"name": "   "})
        long = await http.patch(f"{URL}/{label_id}", json={"name": "가" * 51})
        missing = await http.patch(f"{URL}/{MISSING_ID}", json={"name": "   "})
        names = [x["name"] for x in await labels_of(http) if x["category"] == "budget"]

    # then: 필수·길이·필수 문구의 422(404 아님)이고 '예산 없음'은 그대로다
    assert problem(blank, 422, "invalid-value")["detail"] == REQUIRED
    assert problem(long, 422, "invalid-value")["detail"] == TOO_LONG
    assert problem(missing, 422, "invalid-value")["detail"] == REQUIRED
    assert "예산 없음" in names


async def test_rename_of_a_missing_label_is_404() -> None:
    """없는 Label의 이름을 바꾸면 404다.

    테스트 코드: CL-018
    """
    async with client_for(seeded_use_cases()) as http:
        # when: 없는 id로 이름을 바꾼다
        response = await http.patch(f"{URL}/{MISSING_ID}", json={"name": "아무거나"})

    # then: 404 not-found와 찾을 수 없음 문구다
    detail = problem(response, 404, "not-found")["detail"]
    assert detail == f"BANT Label을(를) 찾을 수 없습니다: {MISSING_ID}"


async def test_unused_labels_are_deleted_whether_default_or_made_by_someone_else() -> None:
    """쓰이지 않는 Label은 기본이든 남이 만든 것이든 삭제되고 그 Label만 사라진다.

    테스트 코드: CL-019
    """
    # given: '예산 없음'과 KIM이 만든 '규제 대응'은 안 쓰이고 '풀 예산 확보'는 Deal이 쓴다
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.SALES) as kim:
        made = (await kim.post(URL, json={"category": "need", "name": "규제 대응"})).json()
    async with client_for(use_cases) as root:
        default = await label_id_of(root, "budget", "예산 없음")
        used = await label_id_of(root, "budget", "풀 예산 확보")
        await use_label(use_cases, used, "budget")

        # when: ROOT가 두 Label을 각각 삭제한다
        first = await root.delete(f"{URL}/{default}")
        second = await root.delete(f"{URL}/{made['id']}")
        names = [x["name"] for x in await labels_of(root)]

    # then: 둘 다 204이고 그 둘만 사라지며 '풀 예산 확보'는 남는다
    assert (first.status_code, second.status_code) == (204, 204)
    assert "예산 없음" not in names
    assert "규제 대응" not in names
    assert "풀 예산 확보" in names
    assert len(names) == BASELINE - 1


async def test_deleting_a_used_label_is_409_with_the_real_deal_count_and_keeps_it() -> None:
    """사용 중인 Label을 지우면 409(실제 Deal 수)이고 Label과 Deal 선택이 그대로다.

    테스트 코드: CL-020
    """
    # given: budget '풀 예산 확보'를 Deal 2건이 선택했다
    use_cases = seeded_use_cases()
    async with client_for(use_cases) as http:
        label_id = await label_id_of(http, "budget", "풀 예산 확보")
        await use_label(use_cases, label_id, "budget", count=2)

        # when: ROOT가 그 Label을 삭제한다
        response = await http.delete(f"{URL}/{label_id}")
        body = await labels_of(http)

    # then: 409 invalid-state '(Deal 2건)'이고 Label은 사용 수 2로 남는다
    assert problem(response, 409, "invalid-state")["detail"] == IN_USE.format(count=2)
    kept = next(x for x in body if x["id"] == label_id)
    assert kept["usage_count"] == 2


async def test_deleting_a_missing_label_is_404() -> None:
    """없는 Label을 삭제하면 404다.

    테스트 코드: CL-023
    """
    async with client_for(seeded_use_cases()) as http:
        # when: 없는 id를 삭제한다
        response = await http.delete(f"{URL}/{MISSING_ID}")

    # then: 404 not-found와 찾을 수 없음 문구다
    detail = problem(response, 404, "not-found")["detail"]
    assert detail == f"BANT Label을(를) 찾을 수 없습니다: {MISSING_ID}"


async def test_a_malformed_label_id_in_the_path_is_request_validation() -> None:
    """경로의 Label id 형식이 틀리면 422 request-validation이다."""
    async with client_for(seeded_use_cases()) as http:
        # when: 정수가 아닌 id로 이름 변경·삭제를 부른다
        patched = await http.patch(f"{URL}/not-an-id", json={"name": "x"})
        deleted = await http.delete(f"{URL}/not-an-id")

    # then: 둘 다 422 request-validation이다
    problem(patched, 422, "request-validation")
    problem(deleted, 422, "request-validation")
