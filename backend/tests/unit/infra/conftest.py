"""ldap3 어댑터 테스트 공통 fixture."""

import pytest

from tests.support.ldap_adapter import PASSWORD
from tests.support.ldap_mock import MockDirectory


@pytest.fixture
def directory() -> MockDirectory:
    mock = MockDirectory()
    mock.add_user("kim", PASSWORD, display_name="김영업", mail="kim@corp.test")
    return mock
