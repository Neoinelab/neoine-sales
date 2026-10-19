import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

const ODD_WON = 1_234_567

describe('상세 인라인 금액: 표기가 같으면 원래 원 값을 유지한다 (AC-8)', () => {
  it('keeps the won amount and history when the same thousands are typed again', async () => {
    const code = await dealCodeOf(2)
    const view = await renderAt(`/deals/${code}`)
    await screen.findByRole('heading', { level: 1, name: '대한제조 MFA 확대' })
    await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: ODD_WON } })
    await view.client.invalidateQueries()
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    await waitFor(() => expect(within(bar).getByText('1,235')).toBeVisible())
    const history = (await gateway.history.list(code, {})).length

    await view.user.click(within(bar).getByRole('button', { name: '금액(단위:천원) 수정' }))
    const input = within(bar).getByLabelText('금액(단위:천원)')
    await view.user.clear(input)
    await view.user.type(input, '1235{Enter}')

    await waitFor(() => expect(within(bar).queryByLabelText('금액(단위:천원)')).not.toBeInTheDocument())
    expect((await gateway.deals.get(code)).revenueAmount).toBe(ODD_WON)
    expect((await gateway.history.list(code, {})).length).toBe(history)
  })
})
