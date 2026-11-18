"""내보내기 쿼리 모델: 목록 조건 키와 같고 offset·limit만 없다 (DL-R33)."""

from app.web.schemas.deal_search import DealExportParams, DealSearchParams


def test_export_params_have_the_list_criteria_without_paging() -> None:
    """DealExportParams의 키는 DealSearchParams에서 offset·limit만 뺀 것과 같다."""
    # when: 두 모델의 필드를 비교한다
    export_keys = set(DealExportParams.model_fields)
    list_keys = set(DealSearchParams.model_fields)
    # then: 조건 키는 그대로이고 페이지 키만 없다
    assert export_keys == list_keys - {"offset", "limit"}
    assert {"offset", "limit"}.isdisjoint(export_keys)
