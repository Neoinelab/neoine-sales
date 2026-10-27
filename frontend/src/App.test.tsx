import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from './test/mockApp'
import { DEFAULT_DEALS_URL_PATTERN } from './test/dealsUrl'

function mainMenu() {
  return within(screen.getByRole('navigation', { name: '주 메뉴' }))
}

describe('목업 표시 없음 (S1)', () => {
  it.each([
    ['로그인 화면', '/login', null],
    ['최초 설정 화면', '/setup', null],
    ['셸(Deals)', '/deals', 'sales'],
    ['Admin 설정 화면', '/admin/integrations', 'admin'],
  ] as const)('shows no mock badge or mock menu on %s', async (_name, url, role) => {
    await renderAt(url, { role })
    await waitFor(() => expect(screen.getAllByRole('heading').length).toBeGreaterThan(0))

    expect(screen.queryByText(/UI 목업/)).not.toBeInTheDocument()
    expect(screen.queryByText(/메모리 저장/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '목업 메뉴' })).not.toBeInTheDocument()
    expect(screen.queryByText(/목업/)).not.toBeInTheDocument()
  })
})

describe('메뉴 (T-SHELL-04~05)', () => {
  it.each(['sales', 'user'] as const)('shows exactly four user menus to %s and no Admin', async (role) => {
    await renderAt('/deals', { role })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    const labels = mainMenu()
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).toEqual(['Dashboard', 'Deals', 'Forecast', 'Reports'])
  })

  it('adds Admin to the four menus for admin only', async () => {
    await renderAt('/deals', { role: 'admin' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    const labels = mainMenu()
      .getAllByRole('link')
      .map((a) => a.textContent)
    expect(labels).toEqual(['Dashboard', 'Deals', 'Forecast', 'Reports', 'Admin'])
  })

  it('shows the signed-in name and role', async () => {
    await renderAt('/deals', { role: 'sales' })
    expect(await screen.findByText('김영업 (sales)')).toBeVisible()
  })

  it('sends the menus to their routes', async () => {
    const { user, location } = await renderAt('/deals', { role: 'admin' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    await user.click(mainMenu().getByRole('link', { name: 'Forecast' }))
    expect(location()).toBe('/forecast')
    await user.click(mainMenu().getByRole('link', { name: 'Admin' }))
    expect(location()).toBe('/admin/users')
  })
})

describe('Reports 화면 (T-SHELL-06, Reports AC1)', () => {
  it('shows the empty report list instead of the coming soon page (/reports)', async () => {
    await renderAt('/reports')
    expect(await screen.findByRole('heading', { name: 'Reports' })).toBeVisible()
    expect(screen.getByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('목업')
  })
})

describe('Dashboard 화면 (Dashboard AC-10)', () => {
  it('shows the Dashboard instead of the coming soon page', async () => {
    await renderAt('/dashboard')
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Forecast' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('목업')
  })

  it.each(['admin', 'sales', 'user'] as const)('is open to the %s role', async (role) => {
    await renderAt('/dashboard', { role })
    expect(await screen.findByRole('tab', { name: 'Status' })).toBeVisible()
  })

  it('sends an anonymous visitor to the login page', async () => {
    const { location } = await renderAt('/dashboard', { role: null })
    await waitFor(() => expect(location()).toBe('/login'))
  })
})

describe('가드와 리다이렉트 (T-SHELL-07~08)', () => {
  it('sends an anonymous visitor to the login page', async () => {
    const { location } = await renderAt('/deals', { role: null })
    await waitFor(() => expect(location()).toBe('/login'))
  })

  it('sends / to the deals list', async () => {
    const { location } = await renderAt('/')
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  it.each(['sales', 'user'] as const)('keeps %s out of the admin pages', async (role) => {
    const { location } = await renderAt('/admin/users', { role })
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  it('opens the admin pages for admin and sends /admin to the user management', async () => {
    const { location } = await renderAt('/admin', { role: 'admin' })
    await waitFor(() => expect(location()).toBe('/admin/users'))
  })

  it('lets only sales and admin open the register and edit routes', async () => {
    const sales = await renderAt('/deals/new', { role: 'sales' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(sales.location()).toBe('/deals/new')
    sales.unmount()

    const admin = await renderAt('/deals/20261001-AB12/edit', { role: 'admin' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(admin.location()).toBe('/deals/20261001-AB12/edit')
    admin.unmount()

    const viewer = await renderAt('/deals/new', { role: 'user' })
    await waitFor(() => expect(viewer.location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    viewer.unmount()

    const viewerEdit = await renderAt('/deals/20261001-AB12/edit', { role: 'user' })
    await waitFor(() => expect(viewerEdit.location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  it('lets everyone open a deal detail and the forecast', async () => {
    const detail = await renderAt('/deals/20261001-AB12', { role: 'user' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(detail.location()).toBe('/deals/20261001-AB12')
    detail.unmount()

    const forecast = await renderAt('/forecast', { role: 'user' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(forecast.location()).toBe('/forecast')
  })

  it.each([
    ['/users', '/admin/users'],
    ['/settings', '/admin/integrations'],
  ])('moves the old address %s to %s for admin', async (from, to) => {
    const { location } = await renderAt(from, { role: 'admin' })
    await waitFor(() => expect(location()).toBe(to))
  })

  it.each(['/customers', '/partners', '/actions', '/nowhere'])('retires %s', async (url) => {
    const { location } = await renderAt(url)
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  it('signs out and returns to the login page', async () => {
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    await user.click(await screen.findByRole('button', { name: '로그아웃' }))
    await waitFor(() => expect(location()).toBe('/login'))
  })
})
