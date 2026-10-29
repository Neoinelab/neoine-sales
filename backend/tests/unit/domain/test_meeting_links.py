"""파트너 회사 해석과 Deal 연결 판정(AC17, P2): 대소문자 무시, 판정 순서."""

import pytest
from app.domain.partner_meeting.errors import DEAL_NOT_FOUND, DEAL_NOT_LINKED
from app.domain.partner_meeting.links import LinkedDeals, deal_link_problem, resolve_company

from tests.factories import make_deal_code

LINKED = LinkedDeals(
    company="한빛파트너스", codes=frozenset({make_deal_code("A001"), make_deal_code("A002")})
)


class TestResolveCompany:
    def test_resolve_company_is_case_insensitive_and_returns_the_representative_spelling(
        self,
    ) -> None:
        assert resolve_company("hanbit PARTNERS", ["Acme", "Hanbit Partners"]) == "Hanbit Partners"

    def test_resolve_company_returns_none_when_no_company_matches(self) -> None:
        assert resolve_company("없는회사", ["한빛파트너스", "Acme"]) is None

    def test_resolve_company_returns_the_first_of_several_matching_spellings(self) -> None:
        assert resolve_company("acme", ["ACME", "Acme"]) == "ACME"

    def test_resolve_company_does_not_trim_or_fuzzy_match(self) -> None:
        assert resolve_company(" Acme", ["Acme"]) is None
        assert resolve_company("Acm", ["Acme"]) is None

    def test_resolve_company_with_no_companies_is_none(self) -> None:
        assert resolve_company("Acme", []) is None


class TestDealLinkProblem:
    def test_a_linked_existing_deal_has_no_problem(self) -> None:
        assert deal_link_problem(make_deal_code("A001"), deal_exists=True, linked=LINKED) is None

    def test_a_missing_code_is_reported_as_deal_not_found(self) -> None:
        assert deal_link_problem(None, deal_exists=False, linked=LINKED) == DEAL_NOT_FOUND

    def test_a_missing_code_is_deal_not_found_even_if_the_flag_says_the_deal_exists(self) -> None:
        assert deal_link_problem(None, deal_exists=True, linked=LINKED) == DEAL_NOT_FOUND

    def test_a_deal_that_does_not_exist_is_deal_not_found_before_the_link_check(self) -> None:
        absent = make_deal_code("ZZZZ")

        assert deal_link_problem(absent, deal_exists=False, linked=LINKED) == DEAL_NOT_FOUND

    def test_an_existing_deal_outside_the_company_is_reported_as_not_linked(self) -> None:
        other = make_deal_code("B777")

        assert deal_link_problem(other, deal_exists=True, linked=LINKED) == DEAL_NOT_LINKED

    @pytest.mark.parametrize("exists", [True, False])
    def test_the_messages_are_the_user_facing_texts(self, exists: bool) -> None:
        assert DEAL_NOT_FOUND == "Deal을 찾을 수 없습니다. 목록에서 다시 선택하세요."
        assert DEAL_NOT_LINKED == "선택한 파트너와 연결된 Deal이 아닙니다."
        assert (
            deal_link_problem(make_deal_code("B777"), deal_exists=exists, linked=LINKED) is not None
        )
