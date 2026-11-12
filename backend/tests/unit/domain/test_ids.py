"""도메인 id 상수: id는 1 이상 2^53-1 이하의 정수다.

새 모듈이라 사용 시점에 가져온다(구현 전에도 같은 디렉터리의 다른 테스트 수집이 막히지 않게).
"""


def test_max_id_is_the_largest_integer_json_represents_exactly() -> None:
    """MAX_ID는 JSON이 정확히 표현하는 가장 큰 정수 2^53-1이다."""
    # when: 상수를 가져온다
    from app.domain.common.ids import MAX_ID  # noqa: PLC0415

    # then: 2^53-1이다
    assert MAX_ID == 2**53 - 1
    assert MAX_ID == 9_007_199_254_740_991
