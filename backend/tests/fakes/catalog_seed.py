"""기본 코드(Status 7, Forecast 6)와 기본 BANT Label 23개. 마이그레이션 시드와 같은 값이다.

실제 DB는 마이그레이션이 시드를 넣으므로 Fake 저장소에도 같은 값을 넣어 출발 상태를 맞춘다.
functional test(tests/functional/admin/test_catalog_seed.py)가 같은 표로 마이그레이션 시드를
검증한다. 확률 힌트의 구분 기호는 목업 시드와 같은 EN DASH(U+2013)다.
"""

from typing import TYPE_CHECKING, Final
from uuid import uuid4

from app.domain.bant.entities import BantLabel
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.code.entities import Code
from app.domain.code.values import CodeId, CodeKey, CodeKind, ForecastOutcome
from tests.factories import NOW

if TYPE_CHECKING:
    from datetime import datetime

    from tests.fakes.unit_of_work import FakeUnitOfWork

EN_DASH: Final = chr(0x2013)
# (key, 이름)
DEFAULT_STATUSES: Final = (
    ("prospecting", "기회발굴"),
    ("introduction", "제품소개"),
    ("poc_preparation", "POC준비"),
    ("poc_completed", "POC완료"),
    ("technical_evaluation", "기술평가"),
    ("price_negotiation", "가격협상"),
    ("contract_completed", "계약완료"),
)
# (key, 이름, outcome, 확률 힌트)
DEFAULT_FORECASTS: Final = (
    ("pipeline", "Pipeline", "open", f"0{EN_DASH}50"),
    ("best", "Best", "open", f"51{EN_DASH}75"),
    ("most_likely", "Most Likely", "open", f"75{EN_DASH}85"),
    ("commit", "Commit", "open", f"85{EN_DASH}100"),
    ("won", "Won", "won", None),
    ("lost", "Lost", "lost", None),
)
# Q5 결정: 참조가 없어도 삭제할 수 없는 코드(이름·순서는 변경 가능)
LOCKED: Final = frozenset(
    {
        ("status", "prospecting"),
        ("status", "contract_completed"),
        ("forecast", "pipeline"),
        ("forecast", "won"),
        ("forecast", "lost"),
    }
)
# PRD 6.4 기본 Label(구분 선언 순, 구분 안에서는 시드 순서 = default_order 1부터)
DEFAULT_LABELS: Final = {
    "budget": (
        "단독 예산 확보",
        "풀 예산 확보",
        "잔여 예산 활용",
        "예산 작업중",
        "내년 예산",
        "예산 없음",
        "미확인",
    ),
    "authority": (
        "CEO 보고 완료",
        "CISO 보고 완료",
        "팀장 보고 완료",
        "팀장 검토",
        "담당자 검토",
        "모름",
    ),
    "need": ("보안 사고 발생", "CISO 지시", "보안 강화 요건", "컴플라이언스", "모름"),
    "timeline": ("금년 구매", "POC 후 일정수립", "기술평가만 진행", "내년구매", "미확정"),
}


def default_codes(now: datetime = NOW) -> list[Code]:
    statuses = [
        Code(
            id=CodeId(uuid4()),
            kind=CodeKind.STATUS,
            key=CodeKey(key),
            name=name,
            order=index,
            outcome=ForecastOutcome.OPEN,
            probability_hint=None,
            created_at=now,
            updated_at=now,
        )
        for index, (key, name) in enumerate(DEFAULT_STATUSES, start=1)
    ]
    forecasts = [
        Code(
            id=CodeId(uuid4()),
            kind=CodeKind.FORECAST,
            key=CodeKey(key),
            name=name,
            order=index,
            outcome=ForecastOutcome(outcome),
            probability_hint=hint,
            created_at=now,
            updated_at=now,
        )
        for index, (key, name, outcome, hint) in enumerate(DEFAULT_FORECASTS, start=1)
    ]
    return [*statuses, *forecasts]


def default_labels(now: datetime = NOW) -> list[BantLabel]:
    return [
        BantLabel(
            id=BantLabelId(uuid4()),
            category=BantCategory(category),
            name=name,
            is_default=True,
            default_order=index,
            created_by_user_id=None,
            created_at=now,
            updated_at=now,
        )
        for category, names in DEFAULT_LABELS.items()
        for index, name in enumerate(names, start=1)
    ]


def seed_catalog(uow: FakeUnitOfWork, now: datetime = NOW) -> None:
    """마이그레이션 시드와 같은 기본 코드·Label을 Fake 저장소에 바로 넣는다(트랜잭션 밖, 준비용)."""
    for code in default_codes(now):
        uow.codes._items[code.id] = code
    for label in default_labels(now):
        uow.bant_labels._items[label.id] = label
