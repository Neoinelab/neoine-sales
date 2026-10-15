import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from './gateway'
import { renderAt } from './test/mockApp'

const MOCK_BADGE = /UI 목업\(가상 데이터\)/

function mainMenu() {
  return within(screen.getByRole('navigation', { name: '주 메뉴' }))
}

describe('목업 배지 (T-SHELL-01~03)', () => {
  it.each([
    ['로그인 화면', '/login', null],
    ['최초 설정 화면', '/setup', null],
    ['셸(Deals)', '/deals', 'sales'],
    ['Admin 설정 화면', '/admin/integrations', 'admin'],
  ] as const)('shows the mock badge on %s', async (_name, url, role) => {
    await renderAt(url, { role })
    expect(await screen.findByText(MOCK_BADGE)).toBeVisible()
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

describe('준비 중 화면 (T-SHELL-06)', () => {
  it.each([
    ['/dashboard', 'Dashboard'],
    ['/reports', 'Reports'],
  ])('shows the coming-soon page for %s', async (url, title) => {
    await renderAt(url)
    expect(await screen.findByRole('heading', { name: title })).toBeVisible()
    expect(screen.getByText(/준비 중입니다/)).toBeVisible()
  })
})

describe('가드와 리다이렉트 (T-SHELL-07~08)', () => {
  it('sends an anonymous visitor to the login page', async () => {
    const { location } = await renderAt('/deals', { role: null })
    await waitFor(() => expect(location()).toBe('/login'))
  })

  it('sends / to the deals list', async () => {
    const { location } = await renderAt('/')
    await waitFor(() => expect(location()).toBe('/deals'))
  })

  it.each(['sales', 'user'] as const)('keeps %s out of the admin pages', async (role) => {
    const { location } = await renderAt('/admin/users', { role })
    await waitFor(() => expect(location()).toBe('/deals'))
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
    await waitFor(() => expect(viewer.location()).toBe('/deals'))
    viewer.unmount()

    const viewerEdit = await renderAt('/deals/20261001-AB12/edit', { role: 'user' })
    await waitFor(() => expect(viewerEdit.location()).toBe('/deals'))
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
    await waitFor(() => expect(location()).toBe('/deals'))
  })

  it('signs out and returns to the login page', async () => {
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    await user.click(await screen.findByRole('button', { name: '로그아웃' }))
    await waitFor(() => expect(location()).toBe('/login'))
  })
})

describe('목업 메뉴 (T-SHELL, 계획 4.5)', () => {
  it('lists the four controls next to the badge', async () => {
    const { user } = await renderAt('/deals', { role: 'admin' })
    await user.click(await screen.findByRole('button', { name: '목업 메뉴' }))
    expect(screen.getByRole('button', { name: '데이터 초기화' })).toBeVisible()
    expect(screen.getByRole('button', { name: '최초 설정 다시 시작' })).toBeVisible()
    expect(screen.getByRole('checkbox', { name: '저장소 장애 시뮬레이션' })).toBeVisible()
    expect(screen.getByRole('checkbox', { name: '지연 끄기' })).toBeVisible()
    expect(screen.getByText(/실제 연동이 아닙니다/)).toBeVisible()
  })

  it('toggles the storage failure simulation', async () => {
    const { user } = await renderAt('/deals', { role: 'admin' })
    await user.click(await screen.findByRole('button', { name: '목업 메뉴' }))
    expect(mockControl.isStorageFailure()).toBe(false)
    await user.click(screen.getByRole('checkbox', { name: '저장소 장애 시뮬레이션' }))
    expect(mockControl.isStorageFailure()).toBe(true)
    await user.click(screen.getByRole('checkbox', { name: '저장소 장애 시뮬레이션' }))
    expect(mockControl.isStorageFailure()).toBe(false)
  })

  it('toggles the response delay', async () => {
    const { user } = await renderAt('/deals', { role: 'admin' })
    await user.click(await screen.findByRole('button', { name: '목업 메뉴' }))
    const before = mockControl.isLatencyOn()
    await user.click(screen.getByRole('checkbox', { name: '지연 끄기' }))
    expect(mockControl.isLatencyOn()).toBe(!before)
  })

  it('restarts the first-time setup: signs out and opens /setup', async () => {
    const { user, location } = await renderAt('/deals', { role: 'admin' })
    await user.click(await screen.findByRole('button', { name: '목업 메뉴' }))
    await user.click(screen.getByRole('button', { name: '최초 설정 다시 시작' }))
    await waitFor(() => expect(location()).toBe('/setup'))
    expect(screen.getByText(MOCK_BADGE)).toBeVisible()
  })

  it('resets the data and says so', async () => {
    const { user } = await renderAt('/deals', { role: 'admin' })
    await user.click(await screen.findByRole('button', { name: '목업 메뉴' }))
    await user.click(screen.getByRole('button', { name: '데이터 초기화' }))
    expect(await screen.findByText('데이터를 처음 상태로 되돌렸습니다.')).toBeVisible()
  })
})
