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

describe('상세 인라인 금액: 원 단위 시작값 (AC-4)', () => {
  it('starts with the exact won value and sends no change when confirmed as is', async () => {
    const { user, bar, code, input } = await openWithOddAmount()
    expect(input).toHaveValue('1,234,567')
    const history = (await gateway.history.list(code, {})).length

    await user.type(input, '{Enter}')

    await waitFor(() => expect(within(bar).queryByLabelText('금액(단위:원)')).not.toBeInTheDocument())
    expect((await gateway.deals.get(code)).revenueAmount).toBe(ODD_WON)
    expect((await gateway.history.list(code, {})).length).toBe(history)
  })

  it('saves the typed won value as is when it differs by less than a thousand', async () => {
    const { user, bar, code, input } = await openWithOddAmount()
    await user.clear(input)
    await user.type(input, '1234000{Enter}')

    await waitFor(() => expect(within(bar).getByText('1,234,000')).toBeVisible())
    expect((await gateway.deals.get(code)).revenueAmount).toBe(1_234_000)
  })
})
