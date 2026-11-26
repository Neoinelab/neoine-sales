import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'
import type { SeedData } from '../../test/fake/store'
import { AMOUNT_INPUT_MESSAGE } from '../../shared/model/money'
import { formFromDeal, validateForm } from './form/formState'

function importedSeed(data: SeedData): SeedData {
  return { ...data, deals: data.deals.map((deal) => ({ ...deal, users: null, revenueAmount: null })) }
}

describe('가져온 Deal의 미입력 숫자', () => {
  it('목록 금액과 빠른 보기 Users count를 대시로 표시한다', async () => {
    // given: 사용자 수와 금액이 없는 가져온 Deal
    const { user } = await renderAt('/deals?year=all&q=대한제조 MFA', { adjustSeed: importedSeed })
    const row = await screen.findByRole('row', { name: /대한제조 MFA 확대/ })
    // when: 목록 행의 빠른 보기를 연다
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    // then: 두 숫자를 0이나 null 문자열 대신 대시로 표시한다
    expect(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('-')
    const quickView = screen.getByRole('region', { name: /빠른 보기: 대한제조 MFA 확대/ })
    expect(within(quickView).getByText('Users count').nextElementSibling).toHaveTextContent('-')
  })

  it('빈 금액의 인라인 편집은 빈 입력으로 시작하고 새 숫자를 저장한다', async () => {
    // given: 매출금액이 없는 가져온 Deal
    const { user } = await renderAt('/deals?year=all&q=대한제조 MFA', { adjustSeed: importedSeed })
    const row = await screen.findByRole('row', { name: /대한제조 MFA 확대/ })
    // when: 빈 금액을 열어 숫자를 입력하고 저장한다
    await user.click(within(row).getByRole('button', { name: /금액\(단위:원\) 편집/ }))
    const input = within(row).getByLabelText('금액(단위:원) 값')
    expect(input).toHaveValue('')
    await user.type(input, '1200{Enter}')
    // then: 숫자 금액이 저장되고 목록에 반영된다
    expect(await within(row).findByRole('button', { name: /금액\(단위:원\) 편집/ })).toHaveTextContent('1,200')
  })

  it('수정 폼은 NULL 숫자를 빈 값으로 열고 필수 입력 검증을 유지한다', async () => {
    // given: 가져온 Deal 조회 결과
    await renderAt('/deals?year=all&q=대한제조 MFA', { adjustSeed: importedSeed })
    const [row] = (await gateway.deals.list({ keyword: '대한제조 MFA' })).items
    if (!row) throw new Error('테스트 Deal이 없습니다')
    const deal = await gateway.deals.get(row.code)
    // when: 수정 폼 초기값을 만들고 검증한다
    const form = formFromDeal(deal, [])
    const errors = validateForm(form, undefined)
    // then: NULL을 숫자로 바꾸지 않고 정상 숫자를 입력해야 저장할 수 있다
    expect(form.users).toBe('')
    expect(form.revenueAmount).toBe('')
    expect(errors.users).toBe('Users count를 입력하세요.')
    expect(errors.revenueAmount).toBe(AMOUNT_INPUT_MESSAGE)
  })
})
