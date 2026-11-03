"""파트너 회사 해석(AC2): 대소문자 무시, 대표 표기 반환. Deal 연결 판정은 없다."""

import importlib

import pytest
from app.domain.partner_meeting.company import resolve_company


def test_resolve_company_returns_the_stored_spelling_ignoring_case() -> None:
    assert resolve_company("hanbit PARTNERS", ["Acme", "Hanbit Partners"]) == "Hanbit Partners"


def test_resolve_company_returns_none_when_no_company_matches() -> None:
    assert resolve_company("없는회사", ["한빛파트너스", "Acme"]) is None


def test_resolve_company_returns_the_first_of_several_matching_spellings() -> None:
    assert resolve_company("acme", ["ACME", "Acme"]) == "ACME"


def test_resolve_company_returns_none_for_partial_or_padded_text() -> None:
    assert resolve_company(" Acme", ["Acme"]) is None
    assert resolve_company("Acm", ["Acme"]) is None


def test_resolve_company_with_no_companies_is_none() -> None:
    assert resolve_company("Acme", []) is None


def test_the_deal_link_module_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.domain.partner_meeting.links")
