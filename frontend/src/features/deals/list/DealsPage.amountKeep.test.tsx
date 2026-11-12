import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { rowOf } from './testHelpers'

const ODD_WON = 1_234_567

/** 시드 Deal의 금액을 1,000의 배수가 아닌 값으로 만들고 목록 행을 연다(표시는 1,234,567). */
async function openOddRow() {
  const view = await renderAt('/deals?q=대한제조 MFA')
  const code = (await gateway.deals.list({ keyword: '대한제조 MFA', limit: 5 })).items[0]!.code
  await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: ODD_WON } })
  await view.client.invalidateQueries()
  const row = await rowOf(/대한제조 MFA 확대/)
  await waitFor(() => expect(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('1,234,567'))
  const history = (await gateway.history.list(code, {})).length
  return { ...view, row, code, history }
}

async function expectUntouched(code: string, history: number) {
  expect((await gateway.deals.get(code)).revenueAmount).toBe(ODD_WON)
  expect((await gateway.history.list(code, {})).length).toBe(history)
  expect(screen.queryByText(/금액.*변경되었습니다/)).not.toBeInTheDocument()
}

describe('목록 인라인 금액: 원 단위 시작값', () => {
  // 원 단위 정확한 값으로 시작하고 바꾸지 않은 Enter는 저장하지 않는다
  // 테스트 코드: DL-094
  it('starts with the exact won value and keeps amount and history when Enter is pressed without a change', async () => {
    // given: 금액 편집기
    const { user, row, code, history } = await openOddRow()
    // when: 금액 편집을 연다
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    // then: 정확한 원 값으로 시작한다
    expect(within(row).getByLabelText('금액(단위:원) 값')).toHaveValue('1,234,567')

    // when: 바꾸지 않고 Enter를 누른다
    await user.keyboard('{Enter}')
    // then: 금액과 이력이 그대로다
    await waitFor(() => expect(within(row).queryByLabelText('금액(단위:원) 값')).not.toBeInTheDocument())
    await expectUntouched(code, history)
  })

  // 1,000원 미만 차이도 다른 값으로 저장한다
  // 테스트 코드: DL-094
  it('saves the typed won value as is when it differs by less than a thousand', async () => {
    // given: 금액 편집기
    const { user, row, code } = await openOddRow()
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:원) 값')
    // when: 1,000원 미만 차이로 바꿔 저장한다
    await user.clear(input)
    await user.type(input, '1234000{Enter}')
    // then: 입력한 원 값이 그대로 저장된다
    await waitFor(() => expect(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('1,234,000'))
    expect((await gateway.deals.get(code)).revenueAmount).toBe(1_234_000)
    expect(await screen.findByText(/금액\(단위:원\)이 '1,234,000'\(으\)로 변경되었습니다\./)).toBeVisible()
  })
})
