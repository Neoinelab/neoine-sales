// 디자이너는 React.lazy 청크이므로 링크를 눌러 열기 전에 미리 읽어 둔다.
import './designer/ReportDesignerPage'
import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { addColumn, openDesigner, resultTable, runQuery, setupReportClock } from '../../test/reportScreen'

setupReportClock()

describe('Reports 목록 (AC1)', () => {
  it.each(['admin', 'sales', 'user'] as const)('shows the empty list and the new report link for %s', async (role) => {
    const { user, location } = await renderAt('/reports', { role })

    expect(await screen.findByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()
    expect(screen.getByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    const link = screen.getByRole('link', { name: '+ 새 리포트' })
    expect(link).toHaveAttribute('href', '/reports/new')

    await user.click(link)

    expect(location()).toBe('/reports/new')
    expect(await screen.findByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
  })

  it('sends an anonymous visitor to the login page', async () => {
    const { location } = await renderAt('/reports', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })

  it('sends an anonymous visitor of the designer to the login page', async () => {
    const { location } = await renderAt('/reports/new', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })
})

describe('user 역할의 디자이너 (AC2)', () => {
  it('lets the user role open the designer and run a query', async () => {
    const { user, location } = await openDesigner({ role: 'user' })
    await addColumn(user, 'Deal code')

    await runQuery(user)

    expect(location()).toBe('/reports/new')
    const table = await screen.findByRole('table', { name: '조회 결과' })
    expect(resultTable()).toBe(table)
    expect(screen.getByRole('cell', { name: 'Deal code 1' })).toBeVisible()
  })

  it('has no permission gate or save button for the user role', async () => {
    await openDesigner({ role: 'user' })

    expect(screen.queryByText(/권한/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /저장/ })).not.toBeInTheDocument()
  })
})
