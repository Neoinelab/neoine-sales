import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, addCondition, chipButton, openDesigner, settingsOf, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

// 저장 안 됨 표시도 role=status라서, 행 단위 안내는 자기 클래스로 가른다.
const scope = (): HTMLElement => {
  const found = screen.getAllByRole('status').find((el) => el.classList.contains('report-scope'))
  if (!found) throw new Error('행 단위 안내 없음')
  return found
}

describe('데이터 범위 표시', () => {
  // 테스트 코드: RQ-073
  it('Action 컬럼을 넣고 빼면 행 단위 안내가 Action 1건과 Deal 1건으로 바뀐다', async () => {
    // given: Deal code 컬럼만 있는 설계
    const { user } = await openDesigner()
    // when: Deal code 컬럼을 넣는다
    await addColumn(user, 'Deal code')

    // then: 행 단위는 Deal 1건이다
    expect(scope()).toHaveTextContent('행 단위: Deal 1건')
    expect(scope()).toHaveClass('scope-deal')

    // when: 진행사항(Action) 컬럼을 넣는다
    await addColumn(user, '진행사항')

    // then: Action 1건과 Join 안내로 바뀐다
    expect(scope()).toHaveTextContent('행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)')
    expect(scope()).toHaveClass('scope-action')

    // when: 진행사항 컬럼을 뺀다
    await user.click(screen.getByRole('button', { name: '진행사항 빼기' }))

    // then: 다시 Deal 1건이다
    expect(scope()).toHaveTextContent('행 단위: Deal 1건')
    expect(scope()).toHaveClass('scope-deal')
  })

  // 테스트 코드: RQ-073
  it('Action 조건만 있으면 EXISTS 안내가 결합(AND/OR)을 따른다', async () => {
    // given: Deal code 컬럼과 진행사항 조건
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    // when: 진행사항 조건을 추가한다
    await addCondition(user, '진행사항')

    // then: AND 안내가 같은 Action 하나가 모든 조건을 만족함을 알린다
    expect(scope()).toHaveTextContent('행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만')
    expect(scope()).toHaveTextContent('(같은 Action 하나가 모든 Action 조건을 만족)')

    // when: 결합을 OR로 바꾼다
    await user.click(screen.getByRole('radio', { name: /OR/ }))

    // then: OR 안내로 바뀐다
    expect(scope()).toHaveTextContent('(Action 조건 중 하나를 만족하는 Action이 있는 Deal)')
    expect(scope()).not.toHaveTextContent('같은 Action 하나가')
  })

  // 테스트 코드: RQ-073
  it('Deal 조건은 Action 거름으로 안내하지 않는다', async () => {
    // given: Deal code 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    // when: Vendor(Deal) 조건을 추가한다
    await addCondition(user, 'Vendor')

    // then: Deal 1건이고 Action 거름 안내가 없다
    expect(scope()).toHaveTextContent('행 단위: Deal 1건')
    expect(scope()).not.toHaveTextContent('Action이 있는 Deal만')
  })

  // 테스트 코드: RQ-073
  it('Deal 숫자 한 번 안내는 Action 행 그룹핑의 합계·평균에서만 보인다', async () => {
    // given: Action 유형과 금액 컬럼
    const { user } = await openDesigner()
    // when: Action 유형과 금액 컬럼을 넣는다
    await addColumn(user, 'Action 유형')
    await addColumn(user, '금액')
    // then: 아직 한 번 안내가 없다
    expect(scope()).not.toHaveTextContent('한 번만 더합니다')

    // when: Action 유형을 그룹핑한다
    await user.click(chipButton(0))
    await user.click(within(settingsOf('Action 유형')).getByRole('checkbox', { name: '그룹핑' }))

    // then: Deal 숫자는 Deal마다 한 번만 더한다는 안내가 보인다
    expect(scope()).toHaveTextContent('Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다')

    // when: 금액 집계를 최소로 바꾼다
    await user.click(chipButton(1))
    await user.selectOptions(within(settingsOf('금액')).getByRole('combobox', { name: '집계' }), 'min')

    // then: 안내가 사라진다
    expect(scope()).not.toHaveTextContent('한 번만 더합니다')
  })
})
