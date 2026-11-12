"""계약 첨부 업로드: 설명의 NUL 문자는 Deal 첨부와 같은 검사로 거절한다(LC-R21 보충)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with
from tests.unit.application.license_contract_env import KIM

if TYPE_CHECKING:
    from tests.unit.application.license_contract_env import ContractEnv

NUL_DESCRIPTION = "설명에는 NUL 문자를 쓸 수 없습니다"


@pytest.mark.parametrize(
    "description",
    ["a\x00b", "가" * 101 + "\x00"],
    ids=["short", "over-100-characters"],
)
async def test_upload_description_with_a_nul_is_rejected_and_nothing_is_left(
    contract_env: ContractEnv, description: str
) -> None:
    """설명에 NUL이 있으면 길이와 무관하게 NUL 문구의 422이고 행·파일이 남지 않는다.

    테스트 코드: LC-085
    """
    # given: 저장 위치가 설정된 미발급 계약
    code = await contract_env.open_deal()
    contract = await contract_env.seed_contract(code)

    # when·then: NUL이 든 설명으로 올리면 설명 길이 문구가 아니라 NUL 문구의 오류다
    with raises_with(InvalidValueError, NUL_DESCRIPTION):
        await contract_env.put_file(contract.id, KIM, description=description)

    # then: 첨부 행과 디스크 파일이 없다
    assert await contract_env.all_file_rows() == []
    assert contract_env.storage.file_count() == 0
