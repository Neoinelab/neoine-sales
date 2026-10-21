"""BANT 선택 판정과 해석: 검증 단계는 읽기만 하고, 새 Label 생성은 검증이 모두 끝난 뒤에 한다.

연락처의 `check_drafts` -> `resolve_contacts`와 같은 구조다.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.ids import new_bant_label_id
from app.domain.bant.entities import BantLabel
from app.domain.bant.rules import find_label
from app.domain.bant.values import BantCategory, BantLabelId, normalize_label_name
from app.domain.deal.errors import InvalidBantLabelError
from app.domain.deal.values import BantSelection

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from app.application.choice import CatalogChoice
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.user.value_objects import UserId


@dataclass(frozen=True, slots=True)
class BantDraft:
    """검증을 통과한 BANT 선택: 있는 Label(선택 안 함 포함)과 새로 만들 이름."""

    chosen: Mapping[BantCategory, BantLabelId | None]
    new_names: Mapping[BantCategory, str]  # 정규화된 이름, 그 구분에 같은 이름이 없음을 확인함


async def check_bant(
    uow: UnitOfWork, choices: Mapping[BantCategory, CatalogChoice | None], *, check: bool
) -> BantDraft:
    """구분마다 판정한다. 읽기만 한다(이름이 있으면 Label을 잠그고 읽는다).

    `{id}`는 check일 때만 그 구분의 Label인지 확인한다. `{name}`은 항상 이름 규칙을 검사하고
    그 구분에서 대소문자 무시로 찾는다.
    """
    has_name = any(c is not None and c.name is not None for c in choices.values())
    labels = await uow.bant_labels.list(for_update=has_name) if check or has_name else []
    known = {label.id: label.category for label in labels}
    chosen: dict[BantCategory, BantLabelId | None] = {}
    new_names: dict[BantCategory, str] = {}
    for category in BantCategory:
        choice = choices.get(category)
        if choice is None:
            chosen[category] = None
        elif choice.id is not None:
            label_id = BantLabelId(choice.id)
            if check and known.get(label_id) is not category:
                raise InvalidBantLabelError
            chosen[category] = label_id
        else:
            name = normalize_label_name(choice.name or "")
            found = find_label([x for x in labels if x.category is category], name)
            if found is None:
                new_names[category] = name
            else:
                chosen[category] = found.id
    return BantDraft(chosen=chosen, new_names=new_names)


async def resolve_bant(
    uow: UnitOfWork, draft: BantDraft, actor_id: UserId, now: datetime
) -> BantSelection:
    """새 이름마다 그 구분에 Label을 만들고 최종 선택을 돌려준다. 검증을 모두 통과한 뒤에 부른다."""
    selected: dict[str, BantLabelId | None] = {}
    for category in BantCategory:
        name = draft.new_names.get(category)
        if name is None:
            selected[category.value] = draft.chosen.get(category)
            continue
        label = BantLabel.create(
            entity_id=await new_bant_label_id(uow.ids),
            category=category,
            name=name,
            created_by=actor_id,
            now=now,
        )
        await uow.bant_labels.add(label)
        selected[category.value] = label.id
    return BantSelection(**selected)
