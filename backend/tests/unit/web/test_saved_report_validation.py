"""저장 리포트 요청 검증 (AC2): 모양은 request-validation, 값은 invalid-value·invalid-report."""

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
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=body)
        listed = await c["alice"].get(URL)

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
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(f"{URL}/{made['id']}", json=body)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    problem(response, 422, "request-validation")
    assert reread.json()["revision"] == 1


@pytest.mark.parametrize(
    "body",
    [{"visibility": "public"}, {"name": 1, "visibility": "public"}, {"name": "x"}],
    ids=["no-name", "name-int", "no-visibility"],
)
async def test_request_shape_errors_are_request_validation_on_copy(body: dict[str, Any]) -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].post(f"{URL}/{made['id']}/copy", json=body)

    problem(response, 422, "request-validation")


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
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(**overrides))
        listed = await c["alice"].get(URL)

    body = problem(response, 422, "invalid-value")
    assert body["detail"] == message
    assert listed.json() == []


async def test_nul_in_name_or_description_is_422_invalid_value() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        in_name = await c["alice"].post(URL, json=create_body(name="a\u0000b"))
        in_description = await c["alice"].post(URL, json=create_body(description="a\u0000b"))

    problem(in_name, 422, "invalid-value")
    problem(in_description, 422, "invalid-value")


async def test_name_and_description_limits_are_inclusive() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(
            URL, json=create_body(name="가" * 100, description="a" * 1000)
        )

    assert response.status_code == 201, response.text


async def test_definition_violations_are_422_invalid_report_with_errors_and_nothing_is_saved() -> (
    None
):
    bad = {"columns": [{"field": "deal.password"}, {"field": "nope.field"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=bad))
        listed = await c["alice"].get(URL)

    body = problem(response, 422, "invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 0, "field"], "unknown-field"),
        (["columns", 1, "field"], "unknown-field"),
    ]
    assert listed.json() == []


async def test_update_with_a_bad_definition_is_422_invalid_report_and_keeps_the_report() -> None:
    bad = {"columns": [{"field": "deal.password"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(f"{URL}/{made['id']}", json=update_body(1, definition=bad))
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    problem(response, 422, "invalid-report")
    assert reread.json()["definition"] == made["definition"]
    assert reread.json()["revision"] == 1


async def test_a_valid_definition_with_conditions_round_trips_through_the_api() -> None:
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
        made = await create(c["alice"], definition=definition)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    stored = reread.json()["definition"]
    assert stored["combine"] == "or"
    assert "sort" not in stored
    assert [c["sort"] for c in stored["columns"]] == [None, "desc"]
    assert stored["row_limit"] == 100
    assert stored["conditions"] == definition["conditions"]
    assert [c["field"] for c in stored["columns"]] == ["deal.vendor", "deal.amount"]


async def test_saved_report_stores_and_returns_column_sort() -> None:
    definition = {"columns": [{"field": "deal.code", "sort": "asc"}, {"field": "deal.name"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=definition)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert [col["sort"] for col in reread.json()["definition"]["columns"]] == ["asc", None]
    assert "sort" not in reread.json()["definition"]


async def test_saved_report_with_unknown_column_sort_is_invalid_report_at_column() -> None:
    bad = {"columns": [{"field": "deal.code"}, {"field": "deal.name", "sort": "up"}]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=bad))

    body = problem(response, 422, "invalid-report")
    assert [(e["location"], e["code"]) for e in body["errors"]] == [
        (["columns", 1, "sort"], "sort-invalid")
    ]


async def test_saved_report_with_top_level_sort_is_request_validation() -> None:
    bad = {"columns": [{"field": "deal.code"}], "sort": {"column": 0, "direction": "asc"}}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=bad))

    problem(response, 422, "request-validation")
