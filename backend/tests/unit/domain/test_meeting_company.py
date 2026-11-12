"""파트너 회사 해석: 대소문자 무시, 대표 표기 반환. Deal 연결 판정은 없다."""

import importlib

import pytest

from app.domain.partner_meeting.company import resolve_company


def test_resolve_company_returns_the_stored_spelling_ignoring_case() -> None:
    """대소문자를 무시하고 등록된 대표 표기를 돌려준다."""
    # when: 대소문자가 다른 이름을 해석한다
    resolved = resolve_company("hanbit PARTNERS", ["Acme", "Hanbit Partners"])
    # then: 등록된 표기다
    assert resolved == "Hanbit Partners"


def test_resolve_company_returns_none_when_no_company_matches() -> None:
    """맞는 회사가 없으면 None이다."""
    # when: 목록에 없는 이름을 해석한다
    resolved = resolve_company("없는회사", ["한빛파트너스", "Acme"])
    # then: None이다
    assert resolved is None


def test_resolve_company_returns_the_first_of_several_matching_spellings() -> None:
    """표기가 여럿이면 첫 번째를 돌려준다."""
    # when: 대소문자만 다른 두 표기가 있는 이름을 해석한다
    resolved = resolve_company("acme", ["ACME", "Acme"])
    # then: 첫 표기다
    assert resolved == "ACME"


def test_resolve_company_returns_none_for_partial_or_padded_text() -> None:
    """공백이 붙었거나 일부만 맞는 이름은 맞지 않는다."""
    # when: 앞에 공백이 붙은 이름과 일부만 맞는 이름을 해석한다
    padded = resolve_company(" Acme", ["Acme"])
    partial = resolve_company("Acm", ["Acme"])
    # then: 둘 다 None이다
    assert padded is None
    assert partial is None


def test_resolve_company_with_no_companies_is_none() -> None:
    """회사 목록이 비어 있으면 None이다."""
    # when: 빈 목록에서 해석한다
    resolved = resolve_company("Acme", [])
    # then: None이다
    assert resolved is None


def test_the_deal_link_module_is_gone() -> None:
    """Deal 연결 판정 모듈은 없다."""
    # when·then: links 모듈을 불러오면 ModuleNotFoundError다
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.domain.partner_meeting.links")
