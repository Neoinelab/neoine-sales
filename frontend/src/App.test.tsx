import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { App } from './App'
import { asMe, authConfig, DIRECTORY_SETTINGS, USER_ROWS } from './test/authFixtures'
import { listPage } from './test/dealFixtures'
import { mockApi, problem, renderApp } from './test/utils'

const adminRoutes = () => ({
  'GET /api/v1/auth/me': { body: asMe('admin') },
  'GET /api/v1/users': { body: { items: USER_ROWS, offset: 0, limit: 50 } },
  'GET /api/v1/settings/directory': { body: DIRECTORY_SETTINGS },
  'GET /api/v1/deals': listPage([]),
  'GET /api/v1/customers': listPage([], 200),
})

describe('App routes (UI-2, UI-6)', () => {
  it('lets admin open the user management page', async () => {
    mockApi(adminRoutes())

    renderApp(<App />, '/users')

    expect(await screen.findByRole('heading', { name: '사용자 관리' })).toBeInTheDocument()
  })

  it('lets admin open the settings page', async () => {
    mockApi(adminRoutes())

    renderApp(<App />, '/settings')

    expect(await screen.findByRole('heading', { name: 'AD 서버 설정' })).toBeInTheDocument()
  })

  it.each([
    ['/users', 'sales'],
    ['/users', 'user'],
    ['/settings', 'sales'],
    ['/settings', 'user'],
  ] as const)('sends %s visitors with role %s to the deal list', async (path, role) => {
    const requests = mockApi({ ...adminRoutes(), 'GET /api/v1/auth/me': { body: asMe(role) } })

    renderApp(<App />, path)

    expect(await screen.findByRole('heading', { name: '딜' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '사용자 관리' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'AD 서버 설정' })).not.toBeInTheDocument()
    expect(requests.some((r) => r.path === '/api/v1/users' || r.path === '/api/v1/settings/directory')).toBe(false)
  })

  it('serves the setup wizard without a session', async () => {
    mockApi({
      'GET /api/v1/auth/me': problem(401, 'unauthenticated', 'x'),
      'GET /api/v1/auth/config': authConfig({ directory_login: false, needs_directory_setup: true }),
    })

    renderApp(<App />, '/setup')

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
  })
})
