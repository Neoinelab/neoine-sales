"""테스트용 엔티티·값 객체 생성 도우미. 기본은 유효한 더미 값이고 overrides로 일부만 바꾼다.

Deal 모델(P1 R2)의 모듈은 이 모듈을 쓰는 모든 테스트가 가져오므로 사용 시점에 가져온다. 새 모델
구현이 없는 동안에도 사용자·코드·연락처 테스트의 수집이 막히면 안 되기 때문이다.
"""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID, OWNER_ID

if TYPE_CHECKING:
    from app.application.deal_action.inputs import ActionContentInput, DealActionInput
    from app.domain.contact.values import ContactId
    from app.domain.deal.code import DealCode
    from app.domain.deal.entities import Deal
    from app.domain.deal.values import DealDetails
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import ActionContent

# 연락처(고객·파트너) 생성 도우미는 `tests/factories_contact.py`다. 이 모듈은 연락처 구현이 없어도
# 가져올 수 있어야 하므로(Deal·사용자 테스트 공용) 연락처 모듈을 모듈 수준에서 가져오지 않는다.

NOW = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
DEAL_DAY = date(2026, 10, 16)  # 팩토리 Deal code의 날짜 부분(YYYYMMDD = 20261016)


def later(seconds: int = 60) -> datetime:
    return NOW + timedelta(seconds=seconds)


def new_contact_id() -> ContactId:
    """저장소에 없는 새 연락처 id(Deal 테스트가 연락처 구현 없이도 id만 필요할 때)."""
    return cast("ContactId", new_id())


def make_deal_code(suffix: str | int = "A001", day: date = DEAL_DAY) -> DealCode:
    """`YYYYMMDD-XXXX`. 정수는 0으로 채운 4자리 숫자 suffix다(7 -> 20261016-0007)."""
    from app.domain.deal.code import DealCode  # noqa: PLC0415 - 지연 import(모듈 설명 참고)

    text = f"{suffix:04d}" if isinstance(suffix, int) else suffix
    return DealCode.issue(day, text)


def make_deal_details(**overrides: Any) -> DealDetails:  # noqa: ANN401
    """overrides: name, owner_user_id, vendor_id, solution, users, revenue_amount(int),
    revenue_date, quote, poc, procurement. revenue_amount는 int를 주면 RevenueAmount로 감싼다."""
    from app.domain.deal.values import (  # noqa: PLC0415
        DealDetails,
        Poc,
        Quote,
        RevenueAmount,
    )

    values: dict[str, Any] = {
        "name": "ERP 구축",
        "owner_user_id": OWNER_ID,
        "vendor_id": None,  # 등록된 Vendor의 id(없으면 선택 안 함)
        "solution": "S/4HANA",  # 자유 텍스트(필수, 앞뒤 공백 제거 후 1~200자)
        "users": 10,
        "revenue_amount": 150_000_000,
        "revenue_date": date(2026, 6, 30),
        "quote": Quote(submitted=None, submitted_date=None),
        "poc": Poc(state=None, completed_date=None),
        "procurement": "",
        **overrides,
    }
    if isinstance(values["revenue_amount"], int):
        values["revenue_amount"] = RevenueAmount(values["revenue_amount"])
    return DealDetails(**values)


def make_bant(**selected: Any) -> Any:  # noqa: ANN401
    """BANT 선택(구분당 Label id 하나 또는 None). 예: make_bant(budget=label.id)."""
    from app.domain.deal.values import BantSelection  # noqa: PLC0415

    return BantSelection(
        **{"budget": None, "authority": None, "need": None, "timeline": None, **selected}
    )


def make_sync(status_key: str = "prospecting", forecast_key: str = "pipeline") -> Any:  # noqa: ANN401
    from app.domain.deal.sync import SyncState  # noqa: PLC0415

    return SyncState(status_key=status_key, forecast_key=forecast_key)


def make_deal(  # noqa: PLR0913 - Deal 생성에 필요한 값이 모두 독립적인 선택지
    now: datetime = NOW,
    *,
    code: str | DealCode | None = None,
    customer_id: ContactId | None = None,
    partner_id: ContactId | None = None,
    status_key: str = "prospecting",
    forecast_key: str = "pipeline",
    bant: Any = None,  # noqa: ANN401
    **detail_overrides: Any,  # noqa: ANN401
) -> Deal:
    """저장하지 않은 Deal. code는 `YYYYMMDD-XXXX` 문자열(또는 DealCode), 생략하면 20261016-A001.

    detail_overrides는 `make_deal_details`와 같다(owner_user_id = Owner).
    """
    from app.domain.deal.code import DealCode  # noqa: PLC0415
    from app.domain.deal.entities import Deal  # noqa: PLC0415

    deal_code = code if isinstance(code, DealCode) else DealCode(code or "20261016-A001")
    return Deal.create(
        code=deal_code,
        details=make_deal_details(**detail_overrides),
        sync=make_sync(status_key, forecast_key),
        customer_id=customer_id or new_contact_id(),
        partner_id=partner_id,
        bant=bant if bant is not None else make_bant(),
        now=now,
    )


def _action_fields(overrides: dict[str, Any]) -> dict[str, Any]:
    """Action 내용 입력의 기본값(유효한 더미)에 overrides를 얹는다. P2 모델: 길이 상한 없음.

    유형은 별도로 다룬다(도메인은 `ActionTypeRef`, 입력은 `CatalogChoice`).
    """
    values: dict[str, Any] = {
        "action": "킥오프 미팅",
        "next_action": "요구사항 문서 전달",
        "due_date": date(2026, 1, 15),
        "memo": "요구사항 정리",
    }
    fields = {**values, **overrides}
    if "due_date" not in overrides and not str(fields["next_action"]).strip():
        fields["due_date"] = None  # Next Action이 없으면 Due Date도 없다(진행사항만 있는 Action)
    return fields


def make_action_content(**overrides: Any) -> ActionContent:  # noqa: ANN401
    """검증을 마친 Action 내용(`ActionContent.parse`). overrides: action_type(유형 이름 문자열
    또는 `ActionTypeRef`, 기본 `미팅`), action, next_action, due_date, memo."""
    from app.domain.deal_action.value_objects import ActionContent  # noqa: PLC0415 - 지연 import
    from tests.factories_action_type import make_type_ref  # noqa: PLC0415

    fields = _action_fields(overrides)
    chosen = fields.pop("action_type", "미팅")
    action_type = make_type_ref(chosen) if isinstance(chosen, str) else chosen
    return ActionContent.parse(action_type=action_type, **fields)


def make_deal_action(
    now: datetime = NOW,
    *,
    deal_code: DealCode | None = None,
    actor_user_id: Any = ACTOR_ID,  # noqa: ANN401
    snapshot: Any = None,  # noqa: ANN401
    entity_id: Any = None,  # noqa: ANN401 - 생략하면 새 10억대 id
    **content_overrides: Any,  # noqa: ANN401
) -> DealAction:
    """저장하지 않은 Action(`DealAction.record`). 수행 시각 = now(`acted_at`을 주면 그 값).

    content_overrides는 `make_action_content`와 같다. 스냅숏 기본은 prospecting/pipeline이다.
    """
    from app.domain.deal_action.entities import DealAction  # noqa: PLC0415 - 지연 import
    from app.domain.deal_action.value_objects import DealActionId  # noqa: PLC0415

    acted_at = content_overrides.pop("acted_at", now)
    return DealAction.record(
        deal_code=deal_code or make_deal_code(),
        content=make_action_content(**content_overrides),
        actor_user_id=actor_user_id,
        snapshot=snapshot or make_sync(),
        now=acted_at,
        entity_id=DealActionId(new_id()) if entity_id is None else entity_id,
    )


def make_deal_action_input(**overrides: Any) -> ActionContentInput:  # noqa: ANN401
    """수정 입력(`ActionContentInput`). overrides는 `make_action_content`와 같되 action_type은
    유형 이름 문자열(`CatalogChoice(name=...)`) 또는 `CatalogChoice`다(기본 `미팅`)."""
    from app.application.choice import CatalogChoice  # noqa: PLC0415 - 지연 import
    from app.application.deal_action.inputs import ActionContentInput  # noqa: PLC0415

    fields = _action_fields(overrides)
    chosen = fields.pop("action_type", "미팅")
    action_type = CatalogChoice(name=chosen) if isinstance(chosen, str) else chosen
    return ActionContentInput(action_type=action_type, **fields)


def make_register_input(
    status_changes: tuple[Any, ...] = (),
    *,
    close_previous_next_action_id: Any = None,  # noqa: ANN401 - DealActionId 또는 None
    **content_overrides: Any,  # noqa: ANN401
) -> DealActionInput:
    """등록 입력(`DealActionInput`): 내용 + 순서대로 적용할 `StatusChangeInput`들.

    close_previous_next_action_id를 주면 저장하면서 그 이전 Next Action을 종료(수행)로 바꾼다
    (R4). 주지 않으면 필드를 아예 넘기지 않아 기본값(None) 동작을 그대로 시험한다.
    """
    from app.application.deal_action.inputs import DealActionInput  # noqa: PLC0415 - 지연 import

    extra: dict[str, Any] = {}
    if close_previous_next_action_id is not None:
        extra["close_previous_next_action_id"] = close_previous_next_action_id
    return DealActionInput(
        content=make_deal_action_input(**content_overrides),
        status_changes=status_changes,
        **extra,
    )
