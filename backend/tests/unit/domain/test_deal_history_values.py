"""Deal History 값: 등록 항목, 구분 값, 연락처 갱신 문구, 이력 항목(R-2·R-7)."""

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
    "comment",
}


def test_created_history_is_the_registration_entry() -> None:
    """등록 이력은 구분 created, 대상·변경 후 'Deal 등록', 변경 전 빈 값이다.

    테스트 코드: DD-041
    """
    # when: 등록 이력 내용을 만든다
    draft = created_draft()

    # then: 구분·대상·전·후가 문서와 같다
    assert draft == HistoryDraft(HistoryCategory("created"), "Deal 등록", "", "Deal 등록")
    assert draft.category == "created"


def test_history_categories_are_exactly_the_thirteen_frontend_values() -> None:
    """이력 구분은 프런트와 같은 정확히 13값이다(comment 포함).

    테스트 코드: DD-040
    """
    # when: 구분 값을 모은다
    actual = {c.value for c in HistoryCategory}
    # then: 13값 집합과 같다
    assert actual == CATEGORIES


@pytest.mark.parametrize("value", sorted(CATEGORIES))
def test_each_frontend_category_value_is_a_member(value: str) -> None:
    """프런트의 구분 값 각각이 이력 구분으로 만들어진다.

    테스트 코드: DD-040
    """
    # when: 구분 값으로 이력 구분을 만든다
    actual = HistoryCategory(value)
    # then: 같은 값이다
    assert actual == value


def test_contact_info_text_lists_title_email_and_phone() -> None:
    """연락처 정보 문구는 직급·이메일·전화를 나열한다."""
    # given: 직급·이메일·전화가 모두 있는 연락처 상세
    details = make_contact_details(title="팀장", email="kim@neoine.example", phone="010-1234-5678")

    # when: 연락처 정보 문구를 만든다
    actual = contact_info_text(details)
    # then: "직급 … · 이메일 … · 전화 …" 형식이다
    assert actual == "직급 팀장 · 이메일 kim@neoine.example · 전화 010-1234-5678"


def test_contact_info_text_uses_a_dash_for_missing_values() -> None:
    """없는 값은 연락처 정보 문구에 대시로 나온다."""
    # given: 직급·이메일·전화가 모두 없는 연락처 상세
    details = make_contact_details(title=None, email=None, phone=None)

    # when: 연락처 정보 문구를 만든다
    actual = contact_info_text(details)
    # then: "직급 - · 이메일 - · 전화 -"다
    assert actual == "직급 - · 이메일 - · 전화 -"


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
    """연락처 변경 대상 문구는 역할·회사·사람 이름을 담는다."""
    # when: 역할별로 변경 대상 문구를 만든다
    actual = contact_change_target(role, make_contact_details())
    # then: 기대한 문구다
    assert actual == expected


def test_history_entry_keeps_its_fields_and_has_no_id_before_saving() -> None:
    """이력 항목은 필드를 그대로 가지고 저장 전에는 id가 없으며 바꿀 수 없다."""
    # given: 등록 이력 내용
    from app.domain.deal.code import DealCode  # noqa: PLC0415

    draft = created_draft()

    # when: 이력 항목을 만든다
    entry = DealHistoryEntry(None, DealCode(CODE), NOW, uid("kim"), draft)

    # then: id가 없고 필드가 같으며 수정은 막힌다
    assert (entry.id, entry.deal_code, entry.changed_at) == (None, DealCode(CODE), NOW)
    assert (entry.changed_by, entry.draft) == (uid("kim"), draft)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.id = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("length", "clipped"), [(299, False), (300, False), (301, True), (1000, True)]
)
def test_a_long_target_is_clipped_to_300_code_points_with_an_ellipsis(
    length: int, clipped: bool
) -> None:
    """대상이 300자를 넘으면 앞 299자 + "…"로 잘리고 300자까지는 그대로다.

    테스트 코드: DD-046
    """
    # given: 길이가 경계값인 대상(이모지는 코드 포인트 하나로 센다)
    target = "😀" * length

    # when: 이력 내용을 만든다
    draft = HistoryDraft(HistoryCategory("other"), target, "", "")

    # then: 300 코드 포인트 이하이고, 넘었을 때만 앞 299자 + "…"다
    assert len(draft.target) == min(length, 300)
    assert (draft.target == "😀" * 299 + "…") is clipped
    assert (draft.target == target) is (not clipped)


@pytest.mark.parametrize(
    ("length", "clipped"), [(999, False), (1000, False), (1001, True), (5000, True)]
)
def test_long_before_and_after_values_are_clipped_to_1000_code_points(
    length: int, clipped: bool
) -> None:
    """변경 전·후 값이 1000자를 넘으면 앞 999자 + "…"로 잘리고 1000자까지는 그대로다.

    테스트 코드: DD-046
    """
    # given: 길이가 경계값인 변경 전·후 값
    text = "가" * length

    # when: 이력 내용을 만든다
    draft = HistoryDraft(HistoryCategory("other"), "Product", text, text)

    # then: 변경 전·후 모두 1000 코드 포인트 이하이고, 넘었을 때만 앞 999자 + "…"다
    for value in (draft.before, draft.after):
        assert len(value) == min(length, 1000)
        assert (value == "가" * 999 + "…") is clipped
