"""코드 종류 잠금 키를 명시 매핑으로 고정한다(R1 리뷰 Minor).

`lock_kind`의 advisory lock 키는 `CodeKind` 선언 순서(index)가 아니라 명시 매핑
`{status: 7_302_001, forecast: 7_302_002}`여야 한다. enum에 멤버를 끼우거나 순서를 바꿔도 운영 중인
다른 인스턴스와 키가 어긋나지 않게 하는 계약이다. 상수로 고정한다:
`app.infra.db.code_repository.KIND_LOCK_KEYS`가 위 매핑과 같다(상수 이름이 계약이다).
"""

from app.domain.code.values import CodeKind

STATUS_KEY = 7_302_001
FORECAST_KEY = 7_302_002
EXPECTED_KEYS = {CodeKind.STATUS: STATUS_KEY, CodeKind.FORECAST: FORECAST_KEY}


def test_the_lock_key_constants_are_an_explicit_mapping_not_the_declaration_order() -> None:
    from app.infra.db.code_repository import KIND_LOCK_KEYS  # noqa: PLC0415

    assert dict(KIND_LOCK_KEYS) == EXPECTED_KEYS
    assert set(KIND_LOCK_KEYS) == set(CodeKind)  # 모든 종류가 키를 가진다
