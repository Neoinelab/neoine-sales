import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { asMe, ME_SALES } from '../../test/authFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { usePermissions } from './hooks'
import { RequireAuth } from './RequireAuth'

const tree = (
  <Routes>
    <Route path="/login" element={<p>로그인 화면</p>} />
    <Route element={<RequireAuth />}>
      <Route path="/deals" element={<p>딜 화면</p>} />
    </Route>
  </Routes>
)

describe('RequireAuth', () => {
  it('redirects anonymous visitors to the login page', async () => {
    mockApi({ 'GET /api/v1/auth/me': problem(401, 'unauthenticated', '로그인이 필요합니다') })

    renderApp(tree, '/deals')

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
  })

  it('renders the page with the signed-in user name and role in the layout', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME_SALES } })

    renderApp(tree, '/deals')

    expect(await screen.findByText('딜 화면')).toBeInTheDocument()
    expect(screen.getByText('김영업 (sales)')).toBeInTheDocument()
  })

  it('signs out through the API and returns to the login page', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: ME_SALES },
      'POST /api/v1/auth/logout': { status: 204 },
    })
    renderApp(tree, '/deals')
    await screen.findByText('딜 화면')

    await userEvent.click(screen.getByRole('button', { name: '로그아웃' }))

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
    const logout = requests.find((r) => r.path === '/api/v1/auth/logout')
    expect(logout?.method).toBe('POST')
    expect(logout?.headers.get('x-requested-with')).toBe('neoine-web')
  })
})

describe('Layout menu by role (UI-6)', () => {
  it('shows the user management and settings menus to admin only', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: asMe('admin') } })

    renderApp(tree, '/deals')

    const nav = await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(nav).toHaveTextContent('사용자 관리')
    expect(screen.getByRole('link', { name: '사용자 관리' })).toHaveAttribute('href', '/users')
    expect(screen.getByRole('link', { name: '설정' })).toHaveAttribute('href', '/settings')
    expect(screen.getByText('최관리 (admin)')).toBeInTheDocument()
  })

  it.each(['sales', 'user'] as const)('hides the admin menus from %s', async (role) => {
    mockApi({ 'GET /api/v1/auth/me': { body: asMe(role) } })

    renderApp(tree, '/deals')

    await screen.findByText('딜 화면')
    expect(screen.getByRole('link', { name: '딜' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '사용자 관리' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '설정' })).not.toBeInTheDocument()
  })

  it('shows the signed-in role for a viewer too', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: asMe('user') } })

    renderApp(tree, '/deals')

    expect(await screen.findByText('조회자 (user)')).toBeInTheDocument()
  })
})

function Probe() {
  const { canWrite, isAdmin } = usePermissions()
  return <p>{`write=${canWrite} admin=${isAdmin}`}</p>
}

describe('usePermissions (UI-9)', () => {
  it.each([
    ['admin', 'write=true admin=true'],
    ['sales', 'write=true admin=false'],
    ['user', 'write=false admin=false'],
  ] as const)('maps role %s to the write and admin flags', async (role, expected) => {
    mockApi({ 'GET /api/v1/auth/me': { body: asMe(role) } })

    renderApp(<Probe />)

    expect(await screen.findByText(expected)).toBeInTheDocument()
  })

  it('denies everything before the user is known and when signed out', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': problem(401, 'unauthenticated', 'x') })

    renderApp(<Probe />)

    expect(screen.getByText('write=false admin=false')).toBeInTheDocument()
    await waitFor(() => expect(requests.some((r) => r.path === '/api/v1/auth/me')).toBe(true))
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(screen.getByText('write=false admin=false')).toBeInTheDocument()
  })
})
