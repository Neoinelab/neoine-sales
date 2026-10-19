import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt, type TestRole } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

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
    await user.keyboard('{Escape}{Escape}') // 첫 Esc는 열린 후보 목록만 닫는다.
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

  it('suggests existing vendors, filters them while typing, and accepts a brand new value', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Vendor 수정' }))
    const input = screen.getByRole('combobox', { name: 'Vendor' })
    await user.clear(input)
    await user.type(input, 'CROWD')
    const list = await screen.findByRole('listbox', { name: 'Vendor' })
    expect(within(list).getAllByRole('option').map((o) => o.textContent)).toEqual(['CrowdStrike'])
    await user.clear(input)
    await user.type(input, 'Zscaler{Enter}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Vendor 수정' })).toHaveTextContent('Zscaler'))
  })

  it('saves Solution as free text and Users as a positive integer', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Solution 수정' }))
    const solution = screen.getByRole('combobox', { name: 'Solution' })
    await user.clear(solution)
    await user.type(solution, 'ITDR Plus{Enter}')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Solution 수정' })).toHaveTextContent('ITDR Plus'))

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

describe('BANT Label 인라인 편집', () => {
  it('changes a label with the select and records it in the history', async () => {
    const { user } = await openDeal(1, '한빛은행 ITDR 도입')
    const bant = screen.getByRole('region', { name: 'BANT' })
    expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('금년 구매')
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.selectOptions(within(bant).getByLabelText('Timeline'), '선택 안 함')
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('—'))
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByRole('cell', { name: 'BANT Label: Timeline' })).toBeVisible()
  })

  it('creates a missing label on the spot and selects it', async () => {
    const { user } = await openDeal(2, '대한제조 MFA 확대')
    const bant = screen.getByRole('region', { name: 'BANT' })
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.selectOptions(within(bant).getByLabelText('Need'), '+ 새 Label 만들기')
    await user.type(within(bant).getByLabelText('Need 새 Label 이름'), '신규 요건{Enter}')
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('신규 요건'))
  })

  it('rejects a duplicate label name and keeps the editor open', async () => {
    const { user } = await openDeal(2, '대한제조 MFA 확대')
    const bant = screen.getByRole('region', { name: 'BANT' })
    await user.click(within(bant).getByRole('button', { name: 'Budget 수정' }))
    await user.selectOptions(within(bant).getByLabelText('Budget'), '+ 새 Label 만들기')
    await user.type(within(bant).getByLabelText('Budget 새 Label 이름'), '단독 예산 확보')
    await user.keyboard('{Enter}')
    expect(await within(bant).findByRole('alert')).toHaveTextContent('같은 구분에 이미 있는 Label 이름입니다.')
    expect(within(bant).getByLabelText('Budget 새 Label 이름')).toBeVisible()
  })
})
