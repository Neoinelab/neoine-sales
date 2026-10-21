import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from './mockApp'

const EMPTY = { seed: 'empty' } as const
const DETAIL_URL = /^\/deals\/\d{8}-[A-Z0-9]{4}$/

describe('업무 데이터가 없는 첫 실행 상태', () => {
  it('shows the empty Deals list with the register button', async () => {
    await renderAt('/deals', EMPTY)
    expect(await screen.findByText('등록된 Deal이 없습니다.')).toBeVisible()
    expect(screen.getByRole('link', { name: '+ Deal 등록' })).toBeVisible()
  })

  it('shows the Forecast screen without crashing when there are no deals', async () => {
    await renderAt('/forecast?year=2026', EMPTY)
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows an empty contacts list for the admin', async () => {
    await renderAt('/admin/contacts', { role: 'admin', ...EMPTY })
    expect(await screen.findByText('등록된 연락처가 없습니다.')).toBeVisible()
  })

  it('still shows the default codes and BANT labels in Deal management', async () => {
    const { user } = await renderAt('/admin/deal', { role: 'admin', ...EMPTY })
    expect(await screen.findByRole('row', { name: /기회발굴/ })).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Forecast 코드' }))
    expect(await screen.findByRole('row', { name: /Commit/ })).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'BANT Label' }))
    const budget = within(await screen.findByRole('region', { name: 'Budget' }))
    expect(await budget.findByText('단독 예산 확보')).toBeVisible()
  })

  it('still lists the login accounts in user management', async () => {
    await renderAt('/admin/users', { role: 'admin', ...EMPTY })
    expect(await screen.findByRole('row', { name: /^kim sales 김영업/ })).toBeVisible()
    expect(screen.getByRole('row', { name: /^root admin 최관리/ })).toBeVisible()
  })

  it('registers the first deal with a typed customer and partner, then adds an action and a file', async () => {
    const { user, location } = await renderAt('/deals/new', EMPTY)
    await screen.findByRole('heading', { name: 'Deal 등록' })
    await user.type(screen.getByLabelText('Deal Name'), '첫 Deal')
    await user.type(screen.getByLabelText('고객 회사명'), '신규고객사')
    await user.type(screen.getByLabelText('고객 담당자명'), '홍길동')
    await user.type(screen.getByLabelText('파트너 회사명'), '신규파트너')
    await user.type(screen.getByLabelText('파트너 담당자명'), '김파트')
    await user.type(screen.getByLabelText('금액(단위:천원)'), '100000')
    await user.type(screen.getByLabelText('Users'), '10')
    fireEvent.change(screen.getByLabelText('Expected Close'), { target: { value: '2027-03-01' } })
    await user.click(screen.getByRole('button', { name: '저장' }))
    await waitFor(() => expect(location()).toMatch(DETAIL_URL))
    expect(await screen.findByRole('heading', { level: 1, name: '첫 Deal' })).toBeVisible()

    // Action 추가
    await user.click(await screen.findByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await user.type(within(form).getByLabelText('유형'), '미팅')
    await user.type(within(form).getByLabelText('진행사항'), '킥오프 미팅')
    await user.type(within(form).getByLabelText('Next Action'), '제안서 전달')
    fireEvent.change(within(form).getByLabelText('Due Date'), { target: { value: '2026-12-01' } })
    await user.click(within(form).getByRole('button', { name: '등록' }))
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    expect(await within(table).findByText('킥오프 미팅')).toBeVisible()

    // 파일 업로드
    const panel = await screen.findByRole('region', { name: '첨부 파일' })
    expect(await within(panel).findByText('첨부된 파일이 없습니다.')).toBeVisible()
    await user.upload(within(panel).getByLabelText('파일'), new File(['x'], '제안서.pdf', { type: 'application/pdf' }))
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    expect(await within(panel).findByRole('button', { name: '제안서.pdf' })).toBeVisible()

    // History 확인
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    const history = await screen.findByRole('table', { name: 'Deal History' })
    expect(await within(history).findByText(/제안서\.pdf/)).toBeVisible()
    expect(within(history).getAllByRole('row').length).toBeGreaterThan(2)
  })
})
