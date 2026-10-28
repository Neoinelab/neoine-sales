import { screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { renderAt } from '../../../test/mockApp'
import { openDesigner, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

describe('필드 목록 (AC3)', () => {
  it('lists deal and action fields and filters by search', async () => {
    const { user } = await openDesigner()

    const deal = screen.getByRole('group', { name: 'Deal' })
    const action = screen.getByRole('group', { name: 'Deal Actions' })
    expect(within(deal).getAllByRole('button', { name: /컬럼에 추가$/ })).toHaveLength(28)
    expect(within(action).getAllByRole('button', { name: /컬럼에 추가$/ })).toHaveLength(12)
    expect(within(deal).getByRole('button', { name: '금액 컬럼에 추가' })).toBeVisible()
    expect(within(action).getByRole('button', { name: 'Action 건수 컬럼에 추가' })).toBeVisible()

    await user.type(screen.getByLabelText('필드 검색'), 'VENDOR')

    expect(screen.getByRole('button', { name: 'Vendor 컬럼에 추가' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Status 컬럼에 추가' })).not.toBeInTheDocument()
  })

  it('matches the display name by part, so BANT finds four fields', async () => {
    const { user } = await openDesigner()

    await user.type(screen.getByLabelText('필드 검색'), 'bant')

    expect(screen.getAllByRole('button', { name: /^BANT .* 컬럼에 추가$/ })).toHaveLength(4)
  })

  it.each([
    ['Deal code', '텍스트'],
    ['Vendor', '코드'],
    ['담당자', '사용자'],
    ['금액', '숫자'],
    ['Expected Close', '날짜'],
    ['등록일', '시각'],
  ])('shows the kind of %s as %s', async (label, kind) => {
    await openDesigner()

    const item = screen.getByRole('button', { name: `${label} 컬럼에 추가` }).closest('li')

    expect(item).not.toBeNull()
    expect(within(item as HTMLElement).getByText(kind)).toBeVisible()
  })

  it('offers the condition button only for fields that can be filtered', async () => {
    await openDesigner()

    expect(screen.getByRole('button', { name: 'Vendor 조건 추가' })).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Action 건수 조건 추가' })).not.toBeInTheDocument()
  })

  it('shows a loading text while the catalog loads', async () => {
    vi.spyOn(gateway.reports, 'fields').mockImplementation(() => new Promise(() => undefined))

    await renderAt('/reports/new')

    expect(await screen.findByText('불러오는 중…')).toBeVisible()
    expect(screen.queryByRole('button', { name: 'Deal code 컬럼에 추가' })).not.toBeInTheDocument()
  })

  it('shows an error and retries when the catalog fails', async () => {
    const failure = new ApiError(500, { type: 'https://x/problems/http-error', title: 't', status: 500, detail: '필드 목록을 불러오지 못했습니다' })
    vi.spyOn(gateway.reports, 'fields').mockRejectedValueOnce(failure)
    const { user } = await renderAt('/reports/new')

    expect(await screen.findByRole('alert')).toHaveTextContent('필드 목록을 불러오지 못했습니다')

    await user.click(screen.getByRole('button', { name: '다시 시도' }))

    expect(await screen.findByRole('button', { name: 'Deal code 컬럼에 추가' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('디자이너 첫 화면 (AC14, AC20)', () => {
  it('shows the title, the reset button and the empty guides', async () => {
    await openDesigner()

    expect(screen.getByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
    expect(screen.getByRole('button', { name: '초기화' })).toBeVisible()
    expect(screen.getByText(/조건이 없으면 모든 Deal이 대상입니다/)).toBeVisible()
    expect(screen.getAllByRole('status').find((el) => el.classList.contains('report-scope'))).toHaveTextContent('행 단위: Deal 1건')
  })

  it('has no chart tab, a save button that waits for a result and no unsaved mark', async () => {
    await openDesigner()

    expect(screen.queryByRole('tab', { name: /차트/ })).not.toBeInTheDocument()
    expect(screen.queryByText('차트')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
    expect(screen.queryByText(/저장 안 됨/)).not.toBeInTheDocument()
  })

  it('disables the run button while there are no columns', async () => {
    await openDesigner()

    expect(screen.getByRole('button', { name: '조회' })).toBeDisabled()
  })
})
