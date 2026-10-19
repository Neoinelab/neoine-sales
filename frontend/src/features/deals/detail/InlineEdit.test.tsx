import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt, type TestRole } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

afterEach(() => vi.restoreAllMocks())

async function openDeal(no: number, title: string, role?: TestRole) {
  const view = await renderAt(await detailPath(no), role === undefined ? {} : { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

describe('수정 버튼 제거와 권한 (클릭 편집)', () => {
  it('has no edit link, no tile edit buttons and no editor pieces on the detail page for a writer', async () => {
    await openDeal(1, '한빛은행 ITDR 도입')
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '고객 연락처 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '파트너 교체' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /새 Label$/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeEnabled()
  })

  it('gives a writer a click-to-edit button on every field value', async () => {
    await openDeal(1, '한빛은행 ITDR 도입')
    const names = [
      'Owner 수정',
      'Vendor 수정',
      'Solution 수정',
      'Users 수정',
      '견적 제출여부 수정',
      '견적 제출일 수정',
      'POC 여부 수정',
      'POC 완료일 수정',
      '구매절차 수정',
      '금액 수정',
      'Expected Close 수정',
      'Status 수정',
      'Forecast 수정',
      'Budget 수정',
      'Authority 수정',
      'Need 수정',
      'Timeline 수정',
      '고객 회사명 수정',
      '고객 담당자명 수정',
      '고객 직급 수정',
      '고객 이메일 수정',
      '고객 전화 수정',
      '파트너 회사명 수정',
      '파트너 담당자명 수정',
      '파트너 직급 수정',
      '파트너 이메일 수정',
      '파트너 전화 수정',
    ]
    for (const name of names) expect(screen.getByRole('button', { name })).toBeVisible()
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
  })

  it('shows a viewer the same values without any click-to-edit control', async () => {
    await openDeal(1, '한빛은행 ITDR 도입', 'user')
    expect(screen.queryAllByRole('button', { name: / 수정$/ })).toHaveLength(0)
    expect(screen.queryByTitle('Deal 이름 수정')).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Deal 정보' })).getByText('김영업')).toBeVisible()
    expect(screen.getByText('Silverfort')).toBeVisible()
    expect(screen.getByText('정민수')).toBeVisible()
    expect(screen.getByText('단독 예산 확보')).toBeVisible()
  })
})

describe('값 클릭 → 입력기 (Enter 저장 / Esc 취소 / 키보드)', () => {
  it('opens the editor with the keyboard (Enter and Space) and focuses the input', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    screen.getByRole('button', { name: 'Vendor 수정' }).focus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('combobox', { name: 'Vendor' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('combobox', { name: 'Vendor' })).not.toBeInTheDocument()
    screen.getByRole('button', { name: 'Solution 수정' }).focus()
    await user.keyboard(' ')
    expect(screen.getByRole('combobox', { name: 'Solution' })).toHaveFocus()
  })

  it('saves the deal name with Enter and shows the success notice', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByTitle('Deal 이름 수정'))
    const input = screen.getByLabelText('Deal 이름')
    await user.clear(input)
    await user.type(input, '한빛은행 ITDR 확장{Enter}')
    expect(await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 확장' })).toBeVisible()
    expect(await screen.findByText('Deal 이름이 변경되었습니다.')).toBeVisible()
  })

  it('discards the typed value with Escape and shows the original value (no buttons)', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    await user.type(screen.getByLabelText('구매절차'), '추가{Escape}')
    expect(screen.queryByLabelText('구매절차')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '구매절차 수정' })).toHaveTextContent('조달청 경쟁 입찰')

    expect(screen.queryByRole('button', { name: /(저장|편집 취소)$/ })).not.toBeInTheDocument()
  })

  it('saves a typed value when focus leaves the input, and does nothing when it is unchanged', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    await user.type(screen.getByLabelText('구매절차'), ' 추가')
    expect(screen.queryByRole('button', { name: /(저장|편집 취소)$/ })).not.toBeInTheDocument()
    await user.tab()
    await waitFor(() => expect(screen.getByRole('button', { name: '구매절차 수정' })).toHaveTextContent('조달청 경쟁 입찰 추가'))
    expect(await screen.findByText('구매절차가 변경되었습니다.')).toBeVisible()

    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    await user.tab()
    expect(screen.getByRole('button', { name: '구매절차 수정' })).toBeVisible()
    expect(screen.queryByLabelText('구매절차')).not.toBeInTheDocument()
  })

  it('keeps the editor open with the message when validation fails on Enter', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByTitle('Deal 이름 수정'))
    await user.clear(screen.getByLabelText('Deal 이름'))
    await user.keyboard('{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal Name을 입력하세요.')
    expect(screen.getByLabelText('Deal 이름')).toBeVisible()
  })
})

describe('Owner · Vendor · Solution · Users · 견적 · POC · 구매절차', () => {
  it('lets the writer pick another sales owner and never offers the resigned one', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Owner 수정' }))
    const select = screen.getByLabelText('Owner')
    expect(within(select).queryByRole('option', { name: '강퇴사(퇴사)' })).not.toBeInTheDocument()
    expect(within(select).queryByRole('option', { name: '한조회' })).not.toBeInTheDocument()
    await user.selectOptions(select, '박영업')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Owner 수정' })).toHaveTextContent('박영업'))
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByRole('cell', { name: 'Owner' })).toBeVisible()
  })

  it('edits Vendor and Solution with selects and never accepts a free text value (AC-11)', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    expect(screen.getByRole('combobox', { name: 'Vendor' }).tagName).toBe('SELECT')
    expect(screen.queryByRole('listbox', { name: 'Vendor' })).not.toBeInTheDocument()
    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    expect(screen.getByRole('combobox', { name: 'Solution' }).tagName).toBe('SELECT')
  })

  it('saves Users as a positive integer', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Users 수정' }))
    const users = screen.getByLabelText('Users')
    await user.clear(users)
    await user.type(users, '0{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Users는 1 이상의 정수로 입력하세요.')
    await user.clear(users)
    await user.type(users, '2500{Enter}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Users 수정' })).toHaveTextContent('2500'))
  })

  it('edits the quote, the POC and the procurement in place', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: '견적 제출여부 수정' }))
    await user.selectOptions(screen.getByLabelText('견적 제출여부'), 'NO')
    await waitFor(() => expect(screen.getByRole('button', { name: '견적 제출여부 수정' })).toHaveTextContent('미제출'))

    await user.click(screen.getByRole('button', { name: 'POC 여부 수정' }))
    await user.selectOptions(screen.getByLabelText('POC 여부'), 'ING')
    await waitFor(() => expect(screen.getByRole('button', { name: 'POC 여부 수정' })).toHaveTextContent('ING'))

    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    const date = screen.getByLabelText('POC 완료일')
    await user.clear(date)
    await user.type(date, '2026-12-01{Enter}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'POC 완료일 수정' })).toHaveTextContent('2026-12-01'))

    await user.click(screen.getByRole('button', { name: '구매절차 수정' }))
    const procurement = screen.getByLabelText('구매절차')
    await user.clear(procurement)
    await user.type(procurement, '수의계약{Enter}')
    await waitFor(() => expect(screen.getByRole('button', { name: '구매절차 수정' })).toHaveTextContent('수의계약'))
  })
})

describe('BANT Label 인라인 편집 (AC-32)', () => {
  async function openBant(no: number, title: string, role?: TestRole) {
    const view = await openDeal(no, title, role)
    return { ...view, bant: screen.getByRole('region', { name: 'BANT' }) }
  }
  const currentLabels = async () => (await gateway.labels.list()).length

  it('opens an autocomplete text input with the current label and has no new-label option', async () => {
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')

    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))

    const input = within(bant).getByRole('combobox', { name: 'Timeline' })
    expect(input.tagName).toBe('INPUT')
    expect(input).toHaveDisplayValue('금년 구매')
    expect(within(bant).queryByRole('option', { name: /새 Label 만들기/ })).not.toBeInTheDocument()
    expect(within(bant).queryByLabelText(/새 Label 이름/)).not.toBeInTheDocument()
  })

  it('lists only the labels of that category', async () => {
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')

    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Need' }))

    const names = within(screen.getByRole('listbox', { name: 'Need' }))
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(names).toEqual(['보안 사고 발생', 'CISO 지시', '보안 강화 요건', '컴플라이언스', '모름'])
  })

  it('saves a picked candidate at once, shows the notice and records the history', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')
    const need = (await gateway.labels.list()).find((l) => l.category === 'need' && l.name === '컴플라이언스')

    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.click(within(bant).getByRole('combobox', { name: 'Need' }))
    await user.click(await screen.findByRole('option', { name: '컴플라이언스' }))

    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('컴플라이언스'))
    expect(await screen.findByText('BANT Need Label이 변경되었습니다.')).toBeVisible()
    expect(update.mock.calls[0]?.[1].bant?.need).toEqual({ id: need?.id })
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByRole('cell', { name: 'BANT Label: Need' })).toBeVisible()
  })

  it('saves a typed new label with Enter, creating it in that category', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')
    const before = await currentLabels()

    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.type(within(bant).getByRole('combobox', { name: 'Need' }), '신규 요건{Enter}')

    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('신규 요건'))
    expect(update.mock.calls[0]?.[1].bant?.need).toEqual({ name: '신규 요건' })
    expect(await currentLabels()).toBe(before + 1)
    expect((await gateway.labels.list()).find((l) => l.name === '신규 요건')).toMatchObject({ category: 'need', isDefault: false })
  })

  it('saves a typed new label when the focus leaves the input', async () => {
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')

    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    const input = within(bant).getByRole('combobox', { name: 'Timeline' })
    await user.clear(input)
    await user.type(input, '내후년 구매 검토')
    await user.tab()

    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('내후년 구매 검토'))
  })

  it('uses the existing label, not a new one, when the typed name equals it', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')
    const before = await currentLabels()
    const budget = (await gateway.labels.list()).find((l) => l.category === 'budget' && l.name === '단독 예산 확보')

    await user.click(within(bant).getByRole('button', { name: 'Budget 수정' }))
    const input = within(bant).getByRole('combobox', { name: 'Budget' })
    await user.clear(input)
    await user.type(input, ' 단독 예산 확보 {Enter}')

    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('단독 예산 확보'))
    expect(update.mock.calls[0]?.[1].bant?.budget).toEqual({ id: budget?.id })
    expect(await currentLabels()).toBe(before)
  })

  it('sends the other categories as they are, so only one category changes', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')
    const labels = await gateway.labels.list()
    const idOf = (category: string, name: string) => labels.find((l) => l.category === category && l.name === name)?.id

    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Need' }))
    await user.keyboard('{Enter}')

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].bant).toEqual({
      budget: { id: idOf('budget', '단독 예산 확보') },
      authority: { id: idOf('authority', 'CISO 보고 완료') },
      need: null,
      timeline: { id: idOf('timeline', '금년 구매') },
    })
  })

  it('clears to not selected when the input is emptied and confirmed', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')

    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Timeline' }))
    await user.keyboard('{Enter}')

    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('—'))
    expect(update.mock.calls[0]?.[1].bant?.timeline).toBeNull()
  })

  it('sends nothing when the value stays the same', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, bant } = await openBant(1, '한빛은행 ITDR 도입')

    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.keyboard('{Enter}')
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.click(within(bant).getByRole('combobox', { name: 'Timeline' }))
    await user.click(await screen.findByRole('option', { name: '금년 구매' }))

    await waitFor(() => expect(within(bant).queryByRole('combobox', { name: 'Timeline' })).not.toBeInTheDocument())
    expect(update).not.toHaveBeenCalled()
    expect(screen.queryByText('BANT Timeline Label이 변경되었습니다.')).not.toBeInTheDocument()
  })

  it('shows the server message for a name over 50 characters and keeps the editor open', async () => {
    const { user, bant } = await openBant(2, '대한제조 MFA 확대')

    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    fireEvent.change(within(bant).getByRole('combobox', { name: 'Need' }), { target: { value: 'x'.repeat(51) } })
    await user.keyboard('{Enter}')

    expect(await within(bant).findByRole('alert')).toHaveTextContent('Label 이름은 50자 이내로 입력하세요.')
    expect(within(bant).getByRole('combobox', { name: 'Need' })).toBeVisible()
  })

  it('does not offer the editor to a viewer', async () => {
    const { bant } = await openBant(1, '한빛은행 ITDR 도입', 'user')

    expect(within(bant).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    expect(within(bant).getByText('단독 예산 확보')).toBeVisible()
  })
})
