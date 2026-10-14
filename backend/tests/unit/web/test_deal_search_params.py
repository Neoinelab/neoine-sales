"""웹 쿼리 모델: owner_user_id(담당자) 필터와 mine=담당자가 나인 딜 (AC10·12)."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.web.schemas.deal import DealSearchParams
from app.web.schemas.deal_stage import PipelineParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")


def test_mine_maps_to_the_viewers_user_id_as_the_owner_condition() -> None:
    query = DealSearchParams(mine=True).to_query(VIEWER)

    assert query.owner_user_id == VIEWER


def test_without_mine_there_is_no_owner_condition() -> None:
    assert DealSearchParams().to_query(VIEWER).owner_user_id is None


def test_mine_false_has_no_owner_condition() -> None:
    assert DealSearchParams(mine=False).to_query(VIEWER).owner_user_id is None


def test_mine_keeps_other_conditions() -> None:
    query = DealSearchParams(mine=True, keyword="erp", offset=3, limit=7).to_query(VIEWER)

    assert (query.keyword, query.offset, query.limit, query.owner_user_id) == (
        "erp",
        3,
        7,
        VIEWER,
    )


def test_mine_is_a_boolean_parameter() -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(mine="maybe")


def test_owner_user_id_parameter_filters_by_that_user() -> None:
    target = uid("someone")

    query = DealSearchParams(owner_user_id=target).to_query(VIEWER)

    assert query.owner_user_id == target


def test_owner_user_id_parameter_must_be_a_uuid() -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(owner_user_id="u-2")


def test_text_owner_parameter_no_longer_exists() -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(owner="박영업")  # type: ignore[call-arg]


def test_owner_user_id_parameter_does_not_need_mine() -> None:
    query = DealSearchParams(owner_user_id=uuid4()).to_query(VIEWER)

    assert query.owner_user_id is not None
    assert query.owner_user_id != VIEWER


def test_pipeline_params_default_to_everyone() -> None:
    assert PipelineParams().mine is False


def test_pipeline_params_accept_mine() -> None:
    assert PipelineParams(mine=True).mine is True


def test_pipeline_params_reject_owner_user_id() -> None:
    with pytest.raises(ValidationError):
        PipelineParams(owner_user_id="u-2")  # type: ignore[call-arg]
