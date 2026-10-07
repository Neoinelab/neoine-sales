import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { mockApi, problem, renderApp } from '../../test/utils'
import { LoginPage } from './LoginPage'
import { RequireAuth } from './RequireAuth'

const ME = { subject: 's', email: 'kim@x.test', name: '김영업', role: 'sales' }

describe('LoginPage', () => {
  it('offers the company login when OIDC is configured', async () => {
    mockApi({ 'GET /api/v1/auth/me': problem(401, 'unauthenticated', 'x'), 'GET /api/v1/auth/config': { body: { oidc: true, dev_login: false } } })

    renderApp(<LoginPage />, '/login')

    const link = await screen.findByRole('link', { name: /회사 계정/ })
    expect(link).toHaveAttribute('href', '/api/v1/auth/login')
    expect(screen.queryByText('개발용 로그인')).not.toBeInTheDocument()
  })

  it('shows the dev login only when the server enables it, and signs in with the chosen role', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': problem(401, 'unauthenticated', 'x'),
      'GET /api/v1/auth/config': { body: { oidc: false, dev_login: true } },
      'POST /api/v1/auth/dev-login': { body: ME },
    })
    renderApp(<LoginPage />, '/login')

    await userEvent.selectOptions(await screen.findByLabelText('역할'), 'admin')
    await userEvent.click(screen.getByRole('button', { name: '개발용으로 로그인' }))

    await waitFor(() => expect(requests.some((r) => r.path === '/api/v1/auth/dev-login')).toBe(true))
    const login = requests.find((r) => r.path === '/api/v1/auth/dev-login')
    expect(login?.body).toEqual({ role: 'admin' })
    expect(login?.headers.get('x-requested-with')).toBe('neoine-web')
    expect(screen.queryByRole('link', { name: /회사 계정/ })).not.toBeInTheDocument()
  })

  it.each([
    ['auth', '로그인에 실패했습니다'],
    ['denied', '권한이 없습니다'],
  ])('explains the %s failure returned by the callback', async (code, text) => {
    mockApi({ 'GET /api/v1/auth/me': problem(401, 'unauthenticated', 'x'), 'GET /api/v1/auth/config': { body: { oidc: true, dev_login: false } } })

    renderApp(<LoginPage />, `/login?error=${code}`)

    expect(await screen.findByRole('alert')).toHaveTextContent(text)
  })
})

describe('RequireAuth', () => {
  const tree = (
    <Routes>
      <Route path="/login" element={<p>로그인 화면</p>} />
      <Route element={<RequireAuth />}>
        <Route path="/deals" element={<p>딜 화면</p>} />
      </Route>
    </Routes>
  )

  it('redirects anonymous visitors to the login page', async () => {
    mockApi({ 'GET /api/v1/auth/me': problem(401, 'unauthenticated', '로그인이 필요합니다') })

    renderApp(tree, '/deals')

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
  })

  it('renders the page with the signed-in user in the layout', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME } })

    renderApp(tree, '/deals')

    expect(await screen.findByText('딜 화면')).toBeInTheDocument()
    expect(screen.getByText('김영업 (sales)')).toBeInTheDocument()
  })
})
