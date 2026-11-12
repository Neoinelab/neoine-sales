"""웹 쿼리 모델: 목록 검색 파라미터가 DealQuery로 바뀌는 방식과 검증.

mine=true는 요청자가 Owner인 딜이고 owner_user_id보다 우선한다.
연/분기·정렬 파라미터는 다른 테스트가 맡는다.
최종 업데이트 기간은 updated_from/to다.
Vendor 조건은 id(int), Solution 조건은 텍스트(부분 일치, 최대 200자)다.
"""

import importlib
from datetime import date

import pytest
from pydantic import ValidationError

from app.application.ports.deal_repository import DealSort, SortOrder
from app.domain.common.errors import InvalidValueError
from app.web.schemas.deal import DealSearchParams
from tests.support.ids import MISSING_ID, new_id
from tests.support.user_ids import uid

VIEWER = uid("viewer")
VENDOR = new_id()


def test_defaults_are_the_first_page_of_twenty_newest_first_without_conditions() -> None:
    """조건 없는 기본 검색은 최신순 첫 페이지 20건이다."""
    # when: 기본 파라미터를 조회 조건으로 바꾼다
    query = DealSearchParams().to_query(VIEWER)

    # then: 첫 페이지 20건, 최종 업데이트 내림차순이고 조건은 없다
    assert (query.offset, query.limit) == (0, 20)
    assert (query.sort, query.order) == (DealSort.LAST_UPDATED_AT, SortOrder.DESC)
    assert query.owner_user_id is None
    assert query.keyword is None


def test_every_basic_condition_reaches_the_query() -> None:
    """기본 조건이 모두 조회 조건에 전달된다."""
    # given: 담당자
    owner = uid("park")

    # when: 모든 기본 조건을 지정해 조회 조건으로 바꾼다
    query = DealSearchParams(
        keyword="erp",
        owner_user_id=owner,
        vendor_id=VENDOR,
        status_key="introduction",
        updated_from=date(2026, 6, 1),
        updated_to=date(2026, 6, 30),
        offset=3,
        limit=7,
    ).to_query(VIEWER)

    # then: 지정한 값이 그대로 전달된다
    assert (query.keyword, query.owner_user_id, query.vendor_id) == ("erp", owner, VENDOR)
    assert query.status_key == "introduction"
    assert (query.updated_from, query.updated_to) == (date(2026, 6, 1), date(2026, 6, 30))
    assert (query.offset, query.limit) == (3, 7)


def test_mine_maps_to_the_viewers_user_id_as_the_owner_condition() -> None:
    """mine=true는 요청자 id를 담당자 조건으로 바꾼다."""
    # when: mine=true를 조회 조건으로 바꾼다
    query = DealSearchParams(mine=True).to_query(VIEWER)

    # then: 담당자 조건이 요청자 id다
    assert query.owner_user_id == VIEWER


def test_without_mine_or_with_mine_false_there_is_no_owner_condition() -> None:
    """mine이 없거나 false면 담당자 조건이 없다."""
    # when: mine 없이, mine=false로 각각 조회 조건으로 바꾼다
    without_mine = DealSearchParams().to_query(VIEWER)
    mine_false = DealSearchParams(mine=False).to_query(VIEWER)

    # then: 둘 다 담당자 조건이 없다
    assert without_mine.owner_user_id is None
    assert mine_false.owner_user_id is None


def test_mine_wins_over_an_explicit_owner() -> None:
    """mine=true는 명시한 담당자보다 우선한다."""
    # when: mine=true와 다른 담당자를 함께 조회 조건으로 바꾼다
    query = DealSearchParams(mine=True, owner_user_id=uid("someone")).to_query(VIEWER)

    # then: 담당자 조건이 요청자 id다
    assert query.owner_user_id == VIEWER


def test_owner_user_id_does_not_need_mine() -> None:
    """owner_user_id는 mine 없이도 쓸 수 있다."""
    # given: 지정할 담당자
    target = uid("someone")

    # when: owner_user_id만 지정해 조회 조건으로 바꾼다
    query = DealSearchParams(owner_user_id=target).to_query(VIEWER)

    # then: 담당자 조건이 그 id다
    assert query.owner_user_id == target


def test_mine_keeps_the_other_conditions() -> None:
    """mine=true여도 다른 조건은 그대로 전달된다."""
    # when: mine과 키워드·페이지를 함께 조회 조건으로 바꾼다
    query = DealSearchParams(mine=True, keyword="erp", offset=3, limit=7).to_query(VIEWER)

    # then: 다른 조건이 그대로고 담당자는 요청자다
    assert (query.keyword, query.offset, query.limit, query.owner_user_id) == (
        "erp",
        3,
        7,
        VIEWER,
    )


@pytest.mark.parametrize("limit", [1, 200])
def test_limit_boundaries_are_accepted(limit: int) -> None:
    """limit의 경계값(1·200)은 허용한다."""
    # when: 경계값 limit으로 파라미터를 만든다
    params = DealSearchParams(limit=limit)

    # then: 값이 그대로다
    assert params.limit == limit


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_page_values_out_of_range_are_rejected(params: dict[str, int]) -> None:
    """범위를 벗어난 페이지 값은 거부한다."""
    # when·then: 범위 밖 limit·offset으로 만들면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize(
    "params",
    [
        {"mine": "maybe"},
        {"owner_user_id": "u-2"},
        {"updated_from": "2026/06/01"},
        {"updated_to": "abc"},
        {"updated_from": "2026-06-01T10:00:00"},
        {"revenue_from": "2026-06-01"},  # 폐지된 파라미터(모르는 키)
        {"revenue_to": "2026-06-30"},
        {"keyword": "a" * 101},
        {"vendor_id": "SAP"},  # 이름이 아니라 정수 id여야 한다
        {"status_key": "a" * 51},
    ],
)
def test_malformed_values_are_rejected(params: dict[str, object]) -> None:
    """형식이 틀린 값은 거부한다."""
    # when·then: 잘못된 값으로 만들면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize(
    "params",
    [
        {"owner": "박영업"},  # 이름 문자열 조건은 없다
        {"vendor": "SAP"},  # 이름 조건은 id 조건(vendor_id)으로 바뀌었다
        {"solution_id": 7},  # 구 id 조건은 폐지됐다
        {"stage": "lost"},
        {"customer_id": MISSING_ID},
        {"partner_id": MISSING_ID},
        {"unknown": "x"},
    ],
)
def test_unknown_or_retired_parameters_are_rejected(params: dict[str, object]) -> None:
    """모르거나 폐지된 파라미터는 거부한다."""
    # when·then: 해당 파라미터를 주면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


def test_the_pipeline_params_model_is_gone() -> None:
    """파이프라인 파라미터 모델은 없어졌다."""
    # when·then: 해당 모듈을 가져오면 ImportError가 난다
    with pytest.raises(ImportError):
        importlib.import_module("app.web.schemas.deal_stage")


def test_vendor_id_is_an_integer() -> None:
    """vendor_id는 정수로 전달된다."""
    # given: 정수 Vendor id
    vendor = new_id()

    # when: 조회 조건으로 바꾼다
    query = DealSearchParams(vendor_id=vendor).to_query(VIEWER)

    # then: 같은 id다
    assert query.vendor_id == vendor


@pytest.mark.parametrize("field", ["owner_user_id", "vendor_id"])
@pytest.mark.parametrize("bad", ["abc", "1.5", "0", "-1", 0, -1, 2**53, "9007199254740992"])
def test_id_query_parameters_must_be_positive_integers(field: str, bad: object) -> None:
    """id 파라미터는 양의 정수여야 한다."""
    # when·then: 문자·소수·0·음수·범위 초과 값이면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**{field: bad})


@pytest.mark.parametrize("field", ["owner_user_id", "vendor_id"])
def test_id_query_parameters_arrive_as_text_and_become_integers(field: str) -> None:
    """문자로 들어온 id 파라미터는 정수가 된다."""
    # when: 문자열 "7"로 검증한다
    params = DealSearchParams.model_validate({field: "7"})

    # then: 정수 7이다
    assert getattr(params, field) == 7


def test_the_largest_allowed_id_query_parameter_is_accepted() -> None:
    """허용되는 가장 큰 id 파라미터(2^53-1)는 받는다."""
    # when: 최댓값 문자열로 검증한다
    params = DealSearchParams.model_validate({"vendor_id": str(2**53 - 1)})

    # then: 정수 최댓값이다
    assert params.vendor_id == 2**53 - 1


def test_vendor_and_solution_conditions_default_to_none() -> None:
    """Vendor·Solution 조건의 기본값은 없음이다."""
    # when: 기본 파라미터를 조회 조건으로 바꾼다
    query = DealSearchParams().to_query(VIEWER)

    # then: 둘 다 None이다
    assert (query.vendor_id, query.solution) == (None, None)


def test_solution_param_is_text() -> None:
    """solution 파라미터는 텍스트로 전달된다."""
    # when: solution 텍스트를 조회 조건으로 바꾼다
    query = DealSearchParams.model_validate({"solution": "itd"}).to_query(VIEWER)

    # then: 같은 텍스트다
    assert query.solution == "itd"


def test_solution_param_is_trimmed_and_blank_means_no_condition() -> None:
    """solution은 공백을 정리하고 공백뿐이면 조건 없음이다."""
    # when: 공백이 든 값과 공백뿐인 값을 각각 조회 조건으로 바꾼다
    trimmed = DealSearchParams(solution="  itd ").to_query(VIEWER)
    blank = DealSearchParams(solution="   ").to_query(VIEWER)

    # then: 앞의 것은 정리되고 뒤의 것은 None이다
    assert (trimmed.solution, blank.solution) == ("itd", None)


def test_solution_param_allows_200_and_rejects_201() -> None:
    """solution은 200자까지 허용하고 201자는 거부한다."""
    # when: 200자 solution을 조회 조건으로 바꾼다
    query = DealSearchParams(solution="a" * 200).to_query(VIEWER)

    # then: 200자 그대로다
    assert query.solution == "a" * 200
    # when·then: 201자로 만들면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(solution="a" * 201)


def test_solution_param_length_is_measured_after_trimming() -> None:
    """solution 길이는 공백 정리 뒤에 잰다."""
    # given: 공백 포함 202자, 정리 후 200자 값
    padded = f" {'a' * 200} "  # 202자이지만 트림 후 200자

    # when: 조회 조건으로 바꾼다
    query = DealSearchParams(solution=padded).to_query(VIEWER)

    # then: 200자로 통과한다
    assert query.solution == "a" * 200


def test_solution_param_over_200_after_trimming_is_rejected() -> None:
    """공백 정리 뒤에도 200자를 넘으면 거부한다."""
    # when·then: 정리 후 201자이면 오류가 난다
    with pytest.raises((ValidationError, InvalidValueError)):
        DealSearchParams(solution=f" {'a' * 201} ").to_query(VIEWER)


def test_solution_id_param_is_rejected() -> None:
    """solution_id 파라미터는 거부한다."""
    # when·then: solution_id를 주면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams.model_validate({"solution_id": "1"})


def test_solution_param_with_nul_is_rejected() -> None:
    """NUL이 든 solution은 거부한다."""
    # when·then: NUL이 든 값이면 오류가 난다
    with pytest.raises((ValidationError, InvalidValueError)):
        DealSearchParams(solution="a\x00b").to_query(VIEWER)


@pytest.mark.parametrize("field", ["updated_from", "updated_to"])
@pytest.mark.parametrize(
    "day", [date(1899, 12, 31), date(3000, 1, 1), date(1, 1, 1), date(9999, 12, 31)]
)
def test_updated_dates_outside_1900_2999_become_invalid_value(field: str, day: date) -> None:
    """1900~2999년 밖의 최종 업데이트 날짜는 잘못된 값이다."""
    # given: 범위 밖 날짜를 가진 파라미터
    params = DealSearchParams(**{field: day})

    # when·then: 조회 조건으로 바꾸면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        params.to_query(VIEWER)


@pytest.mark.parametrize("day", [date(1900, 1, 1), date(2999, 12, 31)])
def test_updated_dates_at_the_range_edges_reach_the_query(day: date) -> None:
    """허용 범위 경계(1900-01-01, 2999-12-31) 날짜는 조회 조건까지 전달된다."""
    # when: 경계 날짜로 조회 조건을 만든다
    query = DealSearchParams(updated_from=day, updated_to=day).to_query(VIEWER)

    window = query.updated_window()

    # then: 기간 조건이 설정된다
    assert window != (None, None)
