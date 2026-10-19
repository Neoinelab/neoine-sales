import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { kvValue } from '../../../test/kvPairs'

async function heading(name: string) {
  return screen.findByRole('heading', { level: 1, name })
}

describe('Deal 상세 상단 (T-DETAIL-01)', () => {
  it('shows the latest status, forecast, amount, expected close and next action in the summary bar', async () => {
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('가격협상')
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit')
    expect(within(bar).getByTitle('1,870,000,000원')).toHaveTextContent('1.87B')
    expect(within(bar).getByText(/계약서 초안 검토/)).toBeVisible()
    expect(within(bar).getByText('Expected Close')).toBeVisible()
  })

  it('shows the deal code and the owner inside the deal info tile', async () => {
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const info = screen.getByRole('region', { name: 'Deal 정보' })
    const code = kvValue(info, 'Deal code').textContent ?? ''
    expect(code).toMatch(/-D001$/)
    expect(code.startsWith('Deal code:')).toBe(false)
    expect(kvValue(info, 'Owner')).toHaveTextContent(/^김영업$/)
  })

  it('shows a resigned owner as 이름(퇴사)', async () => {
    await renderAt(await detailPath(23))
    await heading('한빛은행 PAM')
    expect(kvValue(screen.getByRole('region', { name: 'Deal 정보' }), 'Owner')).toHaveTextContent(/^강퇴사\(퇴사\)$/)
  })

  it('shows the risk badges of an overdue and stale deal', async () => {
    await renderAt(await detailPath(7))
    await heading('하늘카드 AD 보안 강화')
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(bar).getByText('기한초과')).toBeVisible()
    expect(within(bar).getByText('미업데이트')).toBeVisible()
  })

  it('marks a won deal as closed and a lost deal as lost', async () => {
    await renderAt(await detailPath(11))
    await heading('청명대학교 SSO/MFA')
    expect(screen.getByText(/Won으로 종결된 Deal입니다/)).toBeVisible()
  })

  it('marks a lost deal', async () => {
    await renderAt(await detailPath(16))
    await heading('새론병원 SSO')
    expect(screen.getByText(/Lost로 종결된 Deal입니다/)).toBeVisible()
  })
})

describe('Deal 상세 정보 카드 (T-DETAIL-02)', () => {
  it('shows the customer contact with title, email and phone', async () => {
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '고객' })
    expect(within(card).getByText('한빛은행')).toBeVisible()
    expect(within(card).getByText('정민수')).toBeVisible()
    expect(within(card).getByText('과장')).toBeVisible()
  })

  it('shows only the active partner and hides the replaced one inside a collapsed history', async () => {
    await renderAt(await detailPath(17))
    await heading('누리통신 MFA')
    const card = screen.getByRole('region', { name: '파트너' })
    expect(within(card).getAllByText('에이원시스템')[0]).toBeVisible()
    const history = within(card).getByText(/이전 파트너 이력/)
    expect(history.closest('details')).not.toHaveAttribute('open')
    expect(within(card).getByText(/코어테크/)).not.toBeVisible()
  })

  it('says there is no partner when the deal has none', async () => {
    await renderAt(await detailPath(5))
    await heading('누리통신 NGFW 갱신')
    expect(within(screen.getByRole('region', { name: '파트너' })).getByText('파트너 없음')).toBeVisible()
  })

  it('shows the four BANT labels, the quote, the POC and the procurement', async () => {
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const bant = screen.getByRole('region', { name: 'BANT' })
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('단독 예산 확보')
    expect(within(bant).getByRole('button', { name: 'Authority 수정' })).toHaveTextContent('CISO 보고 완료')
    expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('보안 강화 요건')
    expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('금년 구매')
    const info = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(info).getByText(/조달청 경쟁 입찰/)).toBeVisible()
    expect(within(info).getByText('견적')).toBeVisible()
    expect(within(info).getByText('POC')).toBeVisible()
  })

  it('lets a writer change a BANT label and records it in the history', async () => {
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const bant = screen.getByRole('region', { name: 'BANT' })
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.selectOptions(within(bant).getByLabelText('Timeline'), '선택 안 함')
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('—'))
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByRole('cell', { name: 'BANT Label: Timeline' })).toBeVisible()
  })

  it('creates a new BANT label on the spot and selects it', async () => {
    const { user } = await renderAt(await detailPath(2))
    await heading('대한제조 MFA 확대')
    const bant = screen.getByRole('region', { name: 'BANT' })
    await user.click(within(bant).getByRole('button', { name: 'Need 수정' }))
    await user.selectOptions(within(bant).getByLabelText('Need'), '+ 새 Label 만들기')
    await user.type(within(bant).getByLabelText('Need 새 Label 이름'), '신규 요건')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Need 수정' })).toHaveTextContent('신규 요건'))
  })

  it('shows a duplicate label name error from the server', async () => {
    const { user } = await renderAt(await detailPath(2))
    await heading('대한제조 MFA 확대')
    const bant = screen.getByRole('region', { name: 'BANT' })
    await user.click(within(bant).getByRole('button', { name: 'Budget 수정' }))
    await user.selectOptions(within(bant).getByLabelText('Budget'), '+ 새 Label 만들기')
    await user.type(within(bant).getByLabelText('Budget 새 Label 이름'), '단독 예산 확보')
    await user.keyboard('{Enter}')
    expect(await within(bant).findByRole('alert')).toHaveTextContent('같은 구분에 이미 있는 Label 이름입니다.')
  })

  it('edits the customer contact with the contact picker and keeps the other fields', async () => {
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '고객' })
    await user.click(within(card).getByRole('button', { name: '고객 직급 수정' }))
    const title = within(card).getByLabelText('고객 직급')
    await user.clear(title)
    await user.type(title, '팀장')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(card).getByText('팀장')).toBeVisible())
    expect(within(card).getByText('정민수')).toBeVisible()
  })

  it('replaces the partner after warning that the current one becomes inactive', async () => {
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '파트너' })
    await user.click(within(card).getByRole('button', { name: '파트너 회사명 수정' }))
    expect(within(card).getByText(/이력으로 남고 비활성이 됩니다/)).toBeVisible()
    const company = within(card).getByRole('combobox', { name: '파트너 회사명' })
    await user.clear(company)
    await user.type(company, '코어테크')
    const person = within(card).getByRole('combobox', { name: '파트너 담당자명' })
    await user.clear(person)
    await user.type(person, '민지훈')
    await user.click(within(card).getByRole('option', { name: /민지훈/ }))
    await waitFor(() => expect(within(card).getAllByText('코어테크').length).toBeGreaterThan(0))
    expect(within(card).getByText(/이전 파트너 이력/)).toBeVisible()
  })

  it('removes the active partner', async () => {
    const { user } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const card = screen.getByRole('region', { name: '파트너' })
    await user.click(within(card).getByRole('button', { name: '파트너 제거' }))
    await user.click(within(await screen.findByRole('dialog', { name: '파트너 제거' })).getByRole('button', { name: '제거' }))
    await waitFor(() => expect(within(card).getByText('파트너 없음')).toBeVisible())
  })
})

describe('Deal 상세 탭 (T-DETAIL-03)', () => {
  it('has exactly two tabs, Actions and Deal History, and starts on Actions', async () => {
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    const tabs = within(screen.getByRole('tablist', { name: '상세 탭' })).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Actions', 'Deal History'])
    expect(screen.getByRole('tab', { name: 'Actions' })).toHaveAttribute('aria-selected', 'true')
  })

  it('keeps the selected tab in the url', async () => {
    const { user, location } = await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(location()).toMatch(/\?tab=history$/)
  })

  it('opens the history tab straight from the url', async () => {
    await renderAt(await detailPath(1, '?tab=history'))
    await heading('한빛은행 ITDR 도입')
    expect(screen.getByRole('tab', { name: 'Deal History' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('Deal 상세 역할별 버튼과 오류 (T-DETAIL-04)', () => {
  it('gives the owner click-to-edit fields and a delete button, with no edit link', async () => {
    await renderAt(await detailPath(1))
    await heading('한빛은행 ITDR 도입')
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeEnabled()
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', '/deals')
  })

  it('disables delete with a reason for a sales user who is not the owner, but keeps edit', async () => {
    await renderAt(await detailPath(3))
    await heading('미래전자 EDR 교체')
    const del = screen.getByRole('button', { name: 'Deal 삭제' })
    expect(del).toBeDisabled()
    expect(del).toHaveAttribute('title', '본인 Deal 또는 admin만 삭제할 수 있습니다.')
    expect(screen.getByTitle('Deal 이름 수정')).toBeVisible()
  })

  it('lets admin delete anyone s deal', async () => {
    await renderAt(await detailPath(3), { role: 'admin' })
    await heading('미래전자 EDR 교체')
    expect(screen.getByRole('button', { name: 'Deal 삭제' })).toBeEnabled()
  })

  it('shows a viewer the deal without any write control', async () => {
    await renderAt(await detailPath(1), { role: 'user' })
    await heading('한빛은행 ITDR 도입')
    expect(screen.queryByRole('link', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Deal 삭제' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Status')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '금액 수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '고객 회사명 수정' })).not.toBeInTheDocument()
    expect(screen.queryByTitle('Deal 이름 수정')).not.toBeInTheDocument()
    const bant = screen.getByRole('region', { name: 'BANT' })
    expect(within(bant).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    expect(within(bant).getByText('단독 예산 확보')).toBeVisible()
    expect(screen.getByRole('region', { name: 'Deal 정보' })).toHaveTextContent('가격협상')
  })

  it('shows the not found message with a way back', async () => {
    await renderAt('/deals/20000101-ZZZZ')
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', '/deals')
  })
})
