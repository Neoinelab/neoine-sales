# BDD 테스트 케이스를 단위 테스트로 구현하기 (2026-11-09)

feature 문서(`docs/features/<feature>.md`)의 **BDD 테스트 케이스**는 Fake를 쓰는 **단위 테스트**로 구현합니다. functional test(HTTP → 실제 DB end-to-end)는 폐지되었습니다. 실제 DB·어댑터 동작은 Repository 계약 테스트와 infra 단위 테스트(`integration` 마커)가 따로 보장합니다.

## 목차

1. 어디에 무엇으로 구현하나
2. 주석 형식 (backend·frontend 공통)
3. 예시 (pytest)
4. 예시 (Vitest)
5. BDD 밖의 단위 테스트
6. 체크리스트

## 1. 어디에 무엇으로 구현하나

| 문서의 층 | 구현 위치 | 대역 |
| --- | --- | --- |
| backend | 주로 `tests/unit/application/`(유스케이스 하나를 When으로 호출). 권한·검증이 web 계층 규칙이면 `tests/unit/web/` | 모든 Port를 `tests/fakes/`의 Fake로 주입(Fake UoW·Repository·FileStorage·Clock·IdAllocator 등). DB·네트워크 없음 |
| frontend | `frontend/src/features/**/*.test.tsx` | Fake 게이트웨이(`src/test/fake/**`) |

- When은 정확히 하나: backend는 유스케이스 `execute`(또는 web 테스트의 HTTP 호출 하나), frontend는 사용자 조작 하나.
- Then은 관찰 가능한 결과만: 반환값·발생한 도메인 오류(type·문구)·Fake 저장소를 다시 조회한 상태·화면에 보이는 내용. 내부 호출 순서나 Mock 호출 횟수는 검증하지 않습니다.
  - **frontend 예외(2026-11-09 사용자 결정)**: "취소하면 요청을 보내지 않는다"처럼 서버 요청 여부·횟수 자체가 사용자 결과인 경우에 한해 Fake 게이트웨이 spy의 호출 여부·횟수(`not.toHaveBeenCalled`, `toHaveBeenCalledTimes`)를 단언할 수 있습니다. 이때도 화면·Fake 데이터의 결과 상태를 같은 테스트에서 함께 검증합니다. backend는 예외 없음.
- Fake가 실제 구현과 같게 동작하는지는 `tests/unit/repositories/`의 계약 테스트(같은 테스트를 Fake와 SQL에 실행)가 보장합니다. 새 Port에는 Fake와 계약 테스트를 함께 만듭니다.
- 케이스 하나 = 테스트 함수 하나. 같은 케이스의 입력 변형은 `parametrize`로 묶을 수 있습니다(번호는 같게).

## 2. 주석 형식 (backend·frontend 공통)

모든 테스트 함수(새로 쓰거나 고치는 것 + 기존 테스트 전환 대상)는 다음을 갖습니다.

1. **한글 설명**: 어떤 테스트인지 한 문장. pytest는 docstring 첫 줄, Vitest는 `it` 바로 위 주석 또는 `it` 제목.
2. **테스트 코드 번호**: feature 문서의 BDD 케이스를 구현한 테스트만. `테스트 코드: LC-001` (여러 개면 쉼표로).
3. **given / when / then 주석**: 본문 단계 앞에 `# given: …`, `# when: …`, `# then: …` (Vitest는 `//`). 설명은 한국어. Given이 없으면 생략합니다.

함수 이름은 계속 영문 ASCII입니다(`test_<상황>_<기대결과>`, Ruff N802·PLC2401).

## 3. 예시 (pytest)

```python
async def test_issue_rejects_contract_of_non_won_deal(env: LicenseContractEnv) -> None:
    """Won이 아닌 Deal의 미발급 계약은 발급할 수 없다.

    테스트 코드: LC-012
    """
    # given: Won에서 벗어난 Deal과 그 Deal의 미발급 계약
    contract = await env.given_contract(status="not_issued", deal_is_won=False)
    # when: 계약을 발급한다
    with raises_with(LicenseRequiresWonError, DEAL_NOT_WON):
        await env.issue_license(contract.id, start="2026-11-01", term=(1, "year"))
    # then: 계약은 미발급 그대로다
    assert (await env.get(contract.id)).status == "not_issued"
```

BDD 케이스가 아닌 단위 테스트(번호 없음):

```python
def test_license_end_clamps_to_last_day_of_month() -> None:
    """시작일+기간의 같은 날이 없으면 그 달 말일을 종료일로 한다."""
    # when: 1월 31일부터 1개월
    end = license_end(date(2026, 1, 31), Term(1, TermUnit.MONTH))
    # then: 2월 28일
    assert end == date(2026, 2, 28)
```

## 4. 예시 (Vitest)

```tsx
// 테스트 코드: LC-031
it('발급된 계약이 있는 Deal은 Won에서 벗어나려 하면 안내 창만 뜬다', async () => {
  // given: 발급 계약이 있는 Won Deal 상세
  const view = await openDealDetail(11)
  // when: Forecast를 Commit으로 바꾼다
  await view.changeForecast('Commit')
  // then: '라이선스 계약 처리' 안내 창이 뜨고 요청은 보내지 않는다
  expect(await screen.findByRole('dialog', { name: '라이선스 계약 처리' })).toBeVisible()
})
```

## 5. BDD 밖의 단위 테스트

BDD 케이스가 다루지 않는 함수·클래스라도 규칙·경계값·오류 처리가 있으면 `test-engineer`가 판단해 단위 테스트를 추가합니다(값 객체 검증, 날짜 계산, 매퍼, Fake·Repository 계약, 어댑터). 주석 형식(2절)은 같고 테스트 코드 번호만 없습니다.

## 6. 체크리스트

- [ ] feature 문서의 모든 BDD 케이스(폐기 제외)에 같은 번호 주석을 가진 테스트가 있다
- [ ] 문서의 "테스트 위치" 칸이 채워져 있다 (`uv run python scripts/check_feature_trace.py`가 번호·층·위치를 대조)
- [ ] 모든 테스트에 한글 설명과 given(있으면)/when/then 주석이 있다
- [ ] When이 하나이고 Then이 관찰 가능한 결과다
- [ ] 외부 의존은 모두 Fake이며 Mock 호출 횟수 검증이 없다(frontend는 요청 여부가 결과인 경우만 허용, 결과 상태도 함께 검증)
- [ ] 정상·검증 실패·충돌·없음·권한 케이스가 feature마다 있다
