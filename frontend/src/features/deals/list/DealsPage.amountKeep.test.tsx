import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

const ODD_WON = 1_234_567

/** 시드 Deal의 금액을 1000의 배수가 아닌 값으로 만들고 목록 행을 연다(표시는 1,235). */
async function openOddRow() {
  const view = await renderAt('/deals?q=대한제조 MFA')
  const code = (await gateway.deals.list({ keyword: '대한제조 MFA', limit: 5 })).items[0]!.code
  await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: ODD_WON } })
  await view.client.invalidateQueries()
  const row = await rowOf(/대한제조 MFA 확대/)
  await waitFor(() => expect(within(row).getByRole('button', { name: /금액\(단위:천원\) 편집/ })).toHaveTextContent('1,235'))
  const history = (await gateway.history.list(code, {})).length
  return { ...view, row, code, history }
}

async function expectUntouched(code: string, history: number) {
  expect((await gateway.deals.get(code)).revenueAmount).toBe(ODD_WON)
  expect((await gateway.history.list(code, {})).length).toBe(history)
  expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
}

describe('목록 인라인 금액: 표기가 같으면 원래 원 값을 유지한다 (AC-8)', () => {
  it('keeps the won amount and history when Enter is pressed without a change', async () => {
    const { user, row, code, history } = await openOddRow()
    await user.click(within(row).getByRole('button', { name: /금액\(단위:천원\) 편집/ }))
    expect(within(row).getByLabelText('금액(단위:천원) 값')).toHaveValue('1,235')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(row).queryByLabelText('금액(단위:천원) 값')).not.toBeInTheDocument())
    await expectUntouched(code, history)
  })

  it('keeps the won amount and history when the same thousands are typed again', async () => {
    const { user, row, code, history } = await openOddRow()
    await user.click(within(row).getByRole('button', { name: /금액\(단위:천원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:천원) 값')
    await user.clear(input)
    await user.type(input, '1235{Enter}')
    await waitFor(() => expect(within(row).queryByLabelText('금액(단위:천원) 값')).not.toBeInTheDocument())
    await expectUntouched(code, history)
  })
})
