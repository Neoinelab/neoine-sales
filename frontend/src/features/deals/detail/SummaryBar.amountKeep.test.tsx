import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

const ODD_WON = 1_234_567

async function openWithOddAmount() {
  const code = await dealCodeOf(2)
  const view = await renderAt(`/deals/${code}`)
  await screen.findByRole('heading', { level: 1, name: '대한제조 MFA 확대' })
  await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: ODD_WON } })
  await view.client.invalidateQueries()
  const bar = screen.getByRole('region', { name: 'Deal 정보' })
  await waitFor(() => expect(within(bar).getByText('1,234,567')).toBeVisible())
  await view.user.click(within(bar).getByRole('button', { name: '금액(단위:원) 수정' }))
  return { ...view, bar, code, input: within(bar).getByLabelText('금액(단위:원)') }
}

describe('상세 인라인 금액: 원 단위 시작값', () => {
  // 금액 편집은 정확한 원 값으로 시작하고 그대로 확정하면 요청도 이력도 없다.
  // 테스트 코드: DD-104
  it('starts with the exact won value and sends no change when confirmed as is', async () => {
    // given: 천 단위로 떨어지지 않는 금액(1,234,567원)의 Deal
    const { user, bar, code, input } = await openWithOddAmount()
    expect(input).toHaveValue('1,234,567')
    const history = (await gateway.history.list(code, {})).length

    // when: 시작 값 그대로 Enter를 누른다
    await user.type(input, '{Enter}')

    // then: 입력이 '1,234,567'로 시작하고 금액·이력이 그대로다
    await waitFor(() => expect(within(bar).queryByLabelText('금액(단위:원)')).not.toBeInTheDocument())
    expect((await gateway.deals.get(code)).revenueAmount).toBe(ODD_WON)
    expect((await gateway.history.list(code, {})).length).toBe(history)
  })

  // 천 미만 차이도 입력한 원 값 그대로 저장한다.
  // 테스트 코드: DD-104
  it('saves the typed won value as is when it differs by less than a thousand', async () => {
    // given: 금액 1,234,567원 Deal
    const { user, bar, code, input } = await openWithOddAmount()
    // when: 1234000을 입력하고 Enter를 누른다
    await user.clear(input)
    await user.type(input, '1234000{Enter}')

    // then: 금액이 1,234,000으로 저장된다
    await waitFor(() => expect(within(bar).getByText('1,234,000')).toBeVisible())
    expect((await gateway.deals.get(code)).revenueAmount).toBe(1_234_000)
  })
})
