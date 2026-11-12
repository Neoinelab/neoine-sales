"""저장 리포트 요청 검증: 모양은 request-validation, 값은 invalid-value·invalid-report."""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.saved_report_http import (
    URL,
    clients,
    create,
    create_body,
    problem,
    update_body,
)


def _without(body: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in body.items() if k != key}


@pytest.mark.parametrize(
    "body",
    [
        _without(create_body(), "name"),
        _without(create_body(), "visibility"),
        _without(create_body(), "definition"),
        create_body(name=1),
        create_body(description=5),
        create_body(visibility=1),
        create_body(definition="text"),
        create_body(definition={}),
        create_body(definition={"columns": [{"field": "deal.code"}], "unknown": 1}),
        {**create_body(), "extra": True},
    ],
    ids=[
        "no-name",
        "no-visibility",
        "no-definition",
        "name-int",
        "description-int",
        "visibility-int",
        "definition-string",
        "definition-without-columns",
        "definition-unknown-key",
        "unknown-top-level-key",
    ],
)
async def test_request_shape_errors_are_request_validation_on_create(body: dict[str, Any]) -> None:
    """만들기 본문의 모양 오류(모르는 키·누락·타입)는 422 request-validation이고 저장되지 않는다.

    테스트 코드: RS-003
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 모양이 틀린 본문으로 만든다
        response = await c["alice"].post(URL, json=body)
        listed = await c["alice"].get(URL)
    # then: 422 request-validation이고 목록은 비어 있다
    problem(response, 422, "request-validation")
    assert listed.json() == []


@pytest.mark.parametrize(
    "body",
    [
        _without(update_body(), "revision"),
        update_body(revision="3"),
        update_body(revision=0),
        update_body(revision=-1),
        update_body(revision=True),
        update_body(revision=1.5),
        update_body(revision=None),
        _without(update_body(), "name"),
    ],
    ids=[
        "no-revision",
        "revision-string",
        "revision-zero",
        "revision-negative",
        "revision-bool",
        "revision-float",
        "revision-null",
        "no-name",
    ],
)
async def test_request_shape_errors_are_request_validation_on_update(body: dict[str, Any]) -> None:
    """덮어쓰기 본문의 모양 오류(revision 누락·타입 등)는 422 request-validation이고 그대로다.

    테스트 코드: RS-003
    """
    # given: alice의 리포트(revision 1)
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 모양이 틀린 본문으로 덮어쓴다
        response = await c["alice"].put(f"{URL}/{made['id']}", json=body)
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 422 request-validation이고 revision은 그대로 1이다
    problem(response, 422, "request-validation")
    assert reread.json()["revision"] == 1


@pytest.mark.parametrize(
    "body",
    [{"visibility": "public"}, {"name": 1, "visibility": "public"}, {"name": "x"}],
    ids=["no-name", "name-int", "no-visibility"],
)
async def test_request_shape_errors_are_request_validation_on_copy(body: dict[str, Any]) -> None:
    """복제 본문의 모양 오류는 422 request-validation이고 새 리포트가 생기지 않는다.

    테스트 코드: RS-003
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 모양이 틀린 본문으로 복제한다
        response = await c["alice"].post(f"{URL}/{made['id']}/copy", json=body)
        listed = await c["alice"].get(URL)
    # then: 422 request-validation이고 리포트는 하나 그대로다
    problem(response, 422, "request-validation")
    assert len(listed.json()) == 1


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"name": ""}, "리포트 이름을 입력하세요."),
        ({"name": "   "}, "리포트 이름을 입력하세요."),
        ({"name": "가" * 101}, "리포트 이름은 100자 이내로 입력하세요."),
        ({"description": "a" * 1001}, "설명은 1,000자 이내로 입력하세요."),
        ({"visibility": "PUBLIC"}, "공개 범위는 public 또는 private입니다."),
        ({"visibility": "all"}, "공개 범위는 public 또는 private입니다."),
    ],
    ids=[
        "blank-name",
        "spaces-name",
        "long-name",
        "long-description",
        "upper-visibility",
        "unknown",
    ],
)
async def test_value_errors_are_422_invalid_value_with_the_user_message(
    overrides: dict[str, Any], message: str
) -> None:
    """빈 이름·긴 이름·긴 설명·알 수 없는 공개 범위는 422 invalid-value 문구이고 저장되지 않는다.

    테스트 코드: RS-005
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 값이 틀린 메타로 만든다
        response = await c["alice"].post(URL, json=create_body(**overrides))
        listed = await c["alice"].get(URL)
    # then: 422 invalid-value 문구이고 목록은 비어 있다
    body = problem(response, 422, "invalid-value")
    assert body["detail"] == message
    assert listed.json() == []


async def test_nul_in_name_or_description_is_422_invalid_value() -> None:
    """이름·설명의 NUL 문자는 422 invalid-value 문구다.

    테스트 코드: RS-005
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 이름에 NUL, 설명에 NUL을 넣어 각각 만든다
        in_name = await c["alice"].post(URL, json=create_body(name="a\u0000b"))
        in_description = await c["alice"].post(URL, json=create_body(description="a\u0000b"))
    # then: 각각 NUL 문구의 422 invalid-value다
    assert problem(in_name, 422, "invalid-value")["detail"] == (
        "리포트 이름에는 NUL 문자를 쓸 수 없습니다"
    )
    assert problem(in_description, 422, "invalid-value")["detail"] == (
        "설명에는 NUL 문자를 쓸 수 없습니다"
    )


async def test_name_and_description_limits_are_inclusive() -> None:
    """이름 100자와 설명 1,000자는 받는다.

    테스트 코드: RS-004
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 이름 100자·설명 1,000자로 만든다
        response = await c["alice"].post(
            URL, json=create_body(name="가" * 100, description="a" * 1000)
        )
    # then: 201이다
    assert response.status_code == 201, response.text


async def test_definition_violations_are_422_invalid_report_with_errors_and_nothing_is_saved() -> (
    None
):
    """규칙을 어긴 정의는 422 invalid-report(위치·code)이고 저장되지 않는다.

    테스트 코드: RS-006
    """
    # given: 허용되지 않은 필드 둘을 쓰는 정의
    bad = {"columns": [{"field": "deal.password"}, {"field": "nope.field"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 만든다
        response = await c["alice"].post(URL, json=create_body(definition=bad))
        listed = await c["alice"].get(URL)
    # then: 422 invalid-report이고 errors의 (위치, code)가 컬럼마다 있으며 목록은 비어 있다
    body = problem(response, 422, "invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 0, "field"], "unknown-field"),
        (["columns", 1, "field"], "unknown-field"),
    ]
    assert listed.json() == []


async def test_update_with_a_bad_definition_is_422_invalid_report_and_keeps_the_report() -> None:
    """규칙을 어긴 정의로 덮어쓰면 422 invalid-report이고 저장된 리포트는 그대로다.

    테스트 코드: RS-023
    """
    # given: alice의 리포트와 허용되지 않은 필드의 정의
    bad = {"columns": [{"field": "deal.password"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 그 정의로 덮어쓴다
        response = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1, definition=bad))
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 422 invalid-report이고 정의·revision이 그대로다
    problem(response, 422, "invalid-report")
    assert reread.json()["definition"] == made["definition"]
    assert reread.json()["revision"] == 1


async def test_a_valid_definition_with_conditions_round_trips_through_the_api() -> None:
    """조건·정렬·결합·행 수가 있는 정의를 저장하고 다시 읽어도 그대로다."""
    # given: 조건 하나와 컬럼 정렬, or 결합, 행 수 100을 가진 정의
    definition = {
        "columns": [
            {"field": "deal.vendor", "group": True},
            {"field": "deal.amount", "sort": "desc"},
        ],
        "conditions": [
            {
                "field": "deal.expected_close",
                "operator": "relative",
                "value": {"period": "this_year"},
            }
        ],
        "combine": "or",
        "row_limit": 100,
    }
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 저장하고 상세를 다시 읽는다
        made = await create(c["alice"], definition=definition)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    # then: 정의가 그대로이고 최상위 sort는 없다
    stored = reread.json()["definition"]
    assert stored["combine"] == "or"
    assert "sort" not in stored
    assert [c["sort"] for c in stored["columns"]] == [None, "desc"]
    assert stored["row_limit"] == 100
    assert stored["conditions"] == definition["conditions"]
    assert [c["field"] for c in stored["columns"]] == ["deal.vendor", "deal.amount"]


async def test_saved_report_stores_and_returns_column_sort() -> None:
    """컬럼 정렬은 저장되고 상세에서 컬럼마다 돌아온다."""
    # given: 첫 컬럼에만 정렬을 준 정의
    definition = {"columns": [{"field": "deal.code", "sort": "asc"}, {"field": "deal.name"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 저장하고 상세를 다시 읽는다
        made = await create(c["alice"], definition=definition)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    # then: 컬럼 정렬이 ["asc", None]이고 최상위 sort는 없다
    assert [col["sort"] for col in reread.json()["definition"]["columns"]] == ["asc", None]
    assert "sort" not in reread.json()["definition"]


async def test_saved_report_with_unknown_column_sort_is_invalid_report_at_column() -> None:
    """모르는 컬럼 정렬 값으로 저장하면 그 컬럼 위치의 422 invalid-report다."""
    # given: 둘째 컬럼의 정렬이 "up"인 정의
    bad = {"columns": [{"field": "deal.code"}, {"field": "deal.name", "sort": "up"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 그 정의로 저장한다
        response = await c["alice"].post(URL, json=create_body(definition=bad))

    # then: 둘째 컬럼 sort 위치의 sort-invalid 하나다
    body = problem(response, 422, "invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 1, "sort"], "sort-invalid")
    ]


async def test_saved_report_with_top_level_sort_is_request_validation() -> None:
    """예전 최상위 sort를 보내면 422 request-validation이다."""
    # given: 최상위 sort를 가진 정의
    bad = {"columns": [{"field": "deal.code"}], "sort": {"column": 0, "direction": "asc"}}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 그 정의로 저장한다
        response = await c["alice"].post(URL, json=create_body(definition=bad))

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")
