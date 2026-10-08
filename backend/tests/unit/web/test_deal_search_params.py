"""웹 쿼리 모델: mine은 web이 로그인 사용자의 subject로 해석해 DealQuery.owner_user_id가 된다."""

import pytest
from pydantic import ValidationError

from app.web.schemas.deal import DealSearchParams
from app.web.schemas.deal_stage import PipelineParams


def test_mine_maps_to_the_viewer_subject() -> None:
    query = DealSearchParams(mine=True).to_query("u-1")

    assert query.owner_user_id == "u-1"


def test_without_mine_there_is_no_owner_condition() -> None:
    assert DealSearchParams().to_query("u-1").owner_user_id is None


def test_mine_false_has_no_owner_condition() -> None:
    assert DealSearchParams(mine=False).to_query("u-1").owner_user_id is None


def test_mine_keeps_other_conditions() -> None:
    query = DealSearchParams(mine=True, keyword="erp", offset=3, limit=7).to_query("u-1")

    assert (query.keyword, query.offset, query.limit, query.owner_user_id) == ("erp", 3, 7, "u-1")


def test_mine_is_a_boolean_parameter() -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(mine="maybe")


def test_owner_user_id_cannot_be_sent_as_a_parameter() -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(owner_user_id="u-2")  # type: ignore[call-arg]


def test_pipeline_params_default_to_everyone() -> None:
    assert PipelineParams().mine is False


def test_pipeline_params_accept_mine() -> None:
    assert PipelineParams(mine=True).mine is True


def test_pipeline_params_reject_owner_user_id() -> None:
    with pytest.raises(ValidationError):
        PipelineParams(owner_user_id="u-2")  # type: ignore[call-arg]
