"""Reports SQL 생성: 모든 입력 값은 바인딩 파라미터다."""

from tests.support.report_defs import col, cond, resolved
from tests.support.report_sql import flat_params, sql_of

INJECTION = "'; drop table deals; --"


def test_values_are_bound_parameters_not_inlined() -> None:
    """포함 검색어는 SQL 문장에 박히지 않고 바인딩 파라미터로 간다.

    테스트 코드: RQ-058
    """
    # given: SQL 주입 문자열을 검색어로 가진 포함 조건
    report = resolved([col("deal.code")], [cond("deal.name", "contains", INJECTION)])

    # when: 정의의 SQL 문장과 바인딩 파라미터를 만든다
    sql = sql_of(report)
    params = flat_params(report)
    # then: SQL 문장에는 그 문자열이 없고 바인딩 파라미터에만 있다
    assert "drop table" not in sql
    assert any("drop table deals" in str(p) for p in params)


def test_equals_value_is_bound_not_inlined() -> None:
    """같음 검색어도 바인딩 파라미터로 간다.

    테스트 코드: RQ-058
    """
    # given: SQL 주입 문자열을 검색어로 가진 같음 조건
    report = resolved([col("deal.code")], [cond("deal.name", "equals", INJECTION)])

    # when: 정의의 SQL 문장과 바인딩 파라미터를 만든다
    sql = sql_of(report)
    params = flat_params(report)
    # then: SQL 문장에는 없고 바인딩 파라미터에만 있다
    assert "drop table" not in sql
    assert any(INJECTION in str(p) for p in params)


def test_code_list_values_are_bound_not_inlined() -> None:
    """코드 목록 값도 바인딩 파라미터로 간다.

    테스트 코드: RQ-058
    """
    # given: 표식 key를 가진 Status in 조건
    report = resolved([col("deal.code")], [cond("deal.status", "in", ["zz_marker_key"])])

    # when: 정의의 SQL 문장과 바인딩 파라미터를 만든다
    sql = sql_of(report)
    params = flat_params(report)
    # then: SQL 문장에는 없고 바인딩 파라미터에 있다
    assert "zz_marker_key" not in sql
    assert "zz_marker_key" in params


def test_number_values_are_bound_not_inlined() -> None:
    """숫자 값도 바인딩 파라미터로 간다.

    테스트 코드: RQ-058
    """
    # given: 큰 숫자를 가진 금액 같음 조건
    report = resolved([col("deal.code")], [cond("deal.amount", "eq", 987654321)])

    # when: 정의의 SQL 문장과 바인딩 파라미터를 만든다
    sql = sql_of(report)
    params = flat_params(report)
    # then: SQL 문장에는 없고 바인딩 파라미터에 있다
    assert "987654321" not in sql
    assert 987654321 in params


def test_row_limit_is_bound() -> None:
    """행 수 제한도 바인딩 파라미터다.

    테스트 코드: RQ-058
    """
    # given: 행 수 제한 100인 정의
    report = resolved([col("deal.code")], row_limit=100)

    # when: 정의의 바인딩 파라미터를 만든다
    params = flat_params(report)
    # then: 파라미터에 100이 있다
    assert 100 in params


def test_like_wildcards_are_escaped() -> None:
    """포함 검색의 %·_는 글자 그대로 찾도록 이스케이프된다.

    테스트 코드: RQ-058
    """
    # given: %와 _를 포함한 검색어
    report = resolved([col("deal.code")], [cond("deal.name", "contains", "50%_x")])

    # when: 정의의 바인딩 파라미터를 만든다
    params = flat_params(report)
    # then: 파라미터가 이스케이프된 패턴이다
    assert "%50\\%\\_x%" in params


def test_starts_with_escapes_wildcards_and_only_appends_a_trailing_percent() -> None:
    """시작 검색은 와일드카드를 이스케이프하고 뒤에만 %를 붙인다.

    테스트 코드: RQ-058
    """
    # given: %와 _를 포함한 시작 검색어
    report = resolved([col("deal.code")], [cond("deal.name", "starts_with", "50%_x")])

    # when: 정의의 바인딩 파라미터를 만든다
    params = flat_params(report)
    # then: 파라미터가 이스케이프되고 끝에만 %가 붙는다
    assert "50\\%\\_x%" in params


def test_backslash_in_text_is_escaped_for_like() -> None:
    """검색어의 역슬래시도 LIKE용으로 이스케이프된다.

    테스트 코드: RQ-058
    """
    # given: 역슬래시를 포함한 검색어
    report = resolved([col("deal.code")], [cond("deal.name", "contains", "a\\b")])

    # when: 정의의 바인딩 파라미터를 만든다
    params = flat_params(report)
    # then: 파라미터의 역슬래시가 이스케이프된다
    assert "%a\\\\b%" in params
