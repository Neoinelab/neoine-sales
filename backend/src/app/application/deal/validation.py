"""등록·수정 폼 검증: 프런트 목업 `validateDealFields`와 같은 순서·문구(AC-05).

순서: Deal Name -> Vendor·Solution -> Owner -> 매출금액 -> Expected Close -> Users -> Status ->
Forecast -> 동기화 -> BANT Label -> 구매절차 -> 고객 -> 파트너 -> 연락처 형식.
값 자체의 규칙은 도메인 값 객체가 갖고, 여기서는 순서와 저장소를 읽어야 하는 검사(Owner, 코드,
Label)를 맡는다. 저장소를 읽는 검사는 보낸 필드에 대해서만 한다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.deal.contact_draft import CheckedDrafts, check_drafts
from app.domain.bant.values import BantCategory, BantLabelId
from app.domain.code.values import CodeKind
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import (
    FORECAST_REQUIRED_MESSAGE,
    STATUS_REQUIRED_MESSAGE,
    InvalidBantLabelError,
    UnknownCodeError,
)
from app.domain.deal.policy import OWNER_NOT_SALES_MESSAGE, ensure_owner_eligible
from app.domain.deal.sync import SyncState, ensure_sync_consistent
from app.domain.deal.values import (
    BantSelection,
    DealDetails,
    Poc,
    Quote,
    check_amount,
    check_name,
    check_procurement,
    check_solution,
    check_users,
    check_vendor,
)
from app.domain.user.errors import UserNotFoundError
from app.domain.user.value_objects import UserId

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from app.application.deal.form import FormValues
    from app.application.ports.unit_of_work import UnitOfWork

EXPECTED_CLOSE_REQUIRED = "Expected Close를 입력하세요."


@dataclass(frozen=True, slots=True)
class CheckedForm:
    """검증을 통과한 폼: Deal 정보, 상태, BANT 선택, 연락처 입력(보낸 것만)."""

    details: DealDetails
    sync: SyncState
    bant: BantSelection
    drafts: CheckedDrafts


async def validate_form(
    uow: UnitOfWork, values: FormValues, provided: frozenset[str]
) -> CheckedForm:
    """첫 위반에서 InvalidValueError 계열로 거절한다. 저장소 확인은 `provided` 필드만 한다."""
    name = check_name(values.name)
    vendor = check_vendor(values.vendor)
    solution = check_solution(values.solution)
    owner_id = await _owner(uow, values.owner_user_id, "owner_user_id" in provided)
    amount = check_amount(values.revenue_amount)
    if values.revenue_date is None:
        raise InvalidValueError(EXPECTED_CLOSE_REQUIRED)
    users = check_users(values.users)
    sync = await _sync(uow, values, provided)
    bant = await _bant(uow, values.bant, "bant" in provided)
    procurement = check_procurement(values.procurement)
    drafts = check_drafts(values.customer, values.partner)
    details = DealDetails(
        name=name,
        owner_user_id=owner_id,
        vendor=vendor,
        solution=solution,
        users=users,
        revenue_amount=amount,
        revenue_date=values.revenue_date,
        quote=Quote(values.quote_submitted, values.quote_submitted_date),
        poc=Poc(values.poc_state, values.poc_completed_date),
        procurement=procurement,
    )
    return CheckedForm(details=details, sync=sync, bant=bant, drafts=drafts)


async def _owner(uow: UnitOfWork, owner: UUID | None, check: bool) -> UserId:
    """Owner는 재직 중인 sales여야 한다(보낸 경우에만 확인: 같은 값이어도 다시 확인한다)."""
    if owner is None:
        raise InvalidValueError(OWNER_NOT_SALES_MESSAGE)
    owner_id = UserId(owner)
    if check:
        try:
            user = await uow.users.get(owner_id)
        except UserNotFoundError:
            user = None
        ensure_owner_eligible(user)
        if not await uow.users.lock_assignable(owner_id):
            raise InvalidValueError(OWNER_NOT_SALES_MESSAGE)
    return owner_id


async def _sync(uow: UnitOfWork, values: FormValues, provided: frozenset[str]) -> SyncState:
    if "status_key" in provided:
        await _require_code(uow, CodeKind.STATUS, values.status_key, STATUS_REQUIRED_MESSAGE)
    if "forecast_key" in provided:
        await _require_code(uow, CodeKind.FORECAST, values.forecast_key, FORECAST_REQUIRED_MESSAGE)
    state = SyncState(status_key=values.status_key, forecast_key=values.forecast_key)
    if provided & {"status_key", "forecast_key"}:
        ensure_sync_consistent(state)
    return state


async def _require_code(uow: UnitOfWork, kind: CodeKind, key: str, message: str) -> None:
    if all(code.key.value != key for code in await uow.codes.list(kind)):
        raise UnknownCodeError(message)


async def _bant(
    uow: UnitOfWork, chosen: Mapping[BantCategory, UUID | None], check: bool
) -> BantSelection:
    """구분마다 Label id 하나 또는 선택 안 함. 보낸 경우 id가 그 구분의 Label이어야 한다."""
    selected: dict[str, BantLabelId | None] = {}
    known = {label.id: label.category for label in await uow.bant_labels.list()} if check else {}
    for category in BantCategory:
        label_id = chosen.get(category)
        if label_id is not None and check and known.get(BantLabelId(label_id)) is not category:
            raise InvalidBantLabelError
        selected[category.value] = None if label_id is None else BantLabelId(label_id)
    return BantSelection(**selected)
