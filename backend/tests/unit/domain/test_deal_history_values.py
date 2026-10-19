"""Deal History 값: 등록 항목, 구분 값, 연락처 갱신 문구(AC-06·10), 이력 항목(R-2·R-7)."""

import dataclasses

import pytest

from app.domain.contact.values import ContactKind
from app.domain.deal.history import (
    DealHistoryEntry,
    HistoryCategory,
    HistoryDraft,
    contact_change_target,
    contact_info_text,
    created_draft,
)
from tests.factories import NOW
from tests.factories_contact import make_contact_details
from tests.support.history_diff import CODE
from tests.support.user_ids import uid

CATEGORIES = {
    "created",
    "status",
    "forecast",
    "amount",
    "expectedClose",
    "owner",
    "partner",
    "contact",
    "bant",
    "action",
    "attachment",
    "other",
}


def test_created_history_is_the_registration_entry() -> None:
    draft = created_draft()

    assert draft == HistoryDraft(HistoryCategory("created"), "Deal 등록", "", "Deal 등록")
    assert draft.category == "created"


def test_history_categories_are_exactly_the_twelve_frontend_values() -> None:
    assert {c.value for c in HistoryCategory} == CATEGORIES


@pytest.mark.parametrize("value", sorted(CATEGORIES))
def test_each_frontend_category_value_is_a_member(value: str) -> None:
    assert HistoryCategory(value) == value


def test_contact_info_text_lists_title_email_and_phone() -> None:
    details = make_contact_details(title="팀장", email="kim@neoine.example", phone="010-1234-5678")

    assert (
        contact_info_text(details) == "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"
    )


def test_contact_info_text_uses_a_dash_for_missing_values() -> None:
    details = make_contact_details(title=None, email=None, phone=None)

    assert contact_info_text(details) == "직급 - · 이메일 - · 전화 -"


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (ContactKind.CUSTOMER, "고객 연락처 정보 (네오인 김철수)"),
        (ContactKind.PARTNER, "파트너 연락처 정보 (네오인 김철수)"),
    ],
)
def test_contact_change_target_names_the_role_company_and_person(
    role: ContactKind, expected: str
) -> None:
    assert contact_change_target(role, make_contact_details()) == expected


def test_history_entry_keeps_its_fields_and_has_no_id_before_saving() -> None:
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    draft = created_draft()

    entry = DealHistoryEntry(None, DealCode(CODE), NOW, uid("kim"), draft)

    assert (entry.id, entry.deal_code, entry.changed_at) == (None, DealCode(CODE), NOW)
    assert (entry.changed_by, entry.draft) == (uid("kim"), draft)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.id = 1  # type: ignore[misc]
