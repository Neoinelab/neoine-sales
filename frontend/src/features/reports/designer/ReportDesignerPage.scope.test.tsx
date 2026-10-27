import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, addCondition, chipButton, openDesigner, settingsOf, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

const scope = (): HTMLElement => screen.getByRole('status')

describe('데이터 범위 표시 (AC9)', () => {
  it('changes the row scope when an action column is added', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    expect(scope()).toHaveTextContent('행 단위: Deal 1건')
    expect(scope()).toHaveClass('scope-deal')

    await addColumn(user, '진행사항')

    expect(scope()).toHaveTextContent('행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)')
    expect(scope()).toHaveClass('scope-action')

    await user.click(screen.getByRole('button', { name: '진행사항 빼기' }))

    expect(scope()).toHaveTextContent('행 단위: Deal 1건')
    expect(scope()).toHaveClass('scope-deal')
  })

  it('shows exists notes that follow the combine', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, '진행사항')

    expect(scope()).toHaveTextContent('행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만')
    expect(scope()).toHaveTextContent('(같은 Action 하나가 모든 Action 조건을 만족)')

    await user.click(screen.getByRole('radio', { name: /OR/ }))

    expect(scope()).toHaveTextContent('(Action 조건 중 하나를 만족하는 Action이 있는 Deal)')
    expect(scope()).not.toHaveTextContent('같은 Action 하나가')
  })

  it('does not call a Deal condition an Action filter', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')

    expect(scope()).toHaveTextContent('행 단위: Deal 1건')
    expect(scope()).not.toHaveTextContent('Action이 있는 Deal만')
  })

  it('shows exists and deal numbers once notes', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Action 유형')
    await addColumn(user, '금액(원)')
    expect(scope()).not.toHaveTextContent('한 번만 더합니다')

    await user.click(chipButton(0))
    await user.click(within(settingsOf('Action 유형')).getByRole('checkbox', { name: '그룹핑' }))

    expect(scope()).toHaveTextContent('Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다')

    await user.click(chipButton(1))
    await user.selectOptions(within(settingsOf('금액(원)')).getByRole('combobox', { name: '집계' }), 'min')

    expect(scope()).not.toHaveTextContent('한 번만 더합니다')
  })
})
