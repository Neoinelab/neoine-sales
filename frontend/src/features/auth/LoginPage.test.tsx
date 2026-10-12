import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { authConfig, ME_SALES } from '../../test/authFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { LoginPage } from './LoginPage'

const unauthenticated = problem(401, 'unauthenticated', '로그인이 필요합니다')
const FIXED = '아이디 또는 비밀번호가 올바르지 않습니다'

const tree = (
  <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/setup" element={<p>최초 설정 화면</p>} />
    <Route path="/" element={<p>메인 화면</p>} />
  </Routes>
)

async function submit(id = 'kim', password = 'pw-1') {
  await userEvent.type(await screen.findByLabelText('AD 아이디'), id)
  await userEvent.type(screen.getByLabelText('비밀번호'), password)
  await userEvent.click(screen.getByRole('button', { name: '로그인' }))
}

/** 로그인에 성공하기 전에는 401, 성공한 뒤에는 사용자를 돌려주는 me. */
function sessionAfterLogin() {
  let signedIn = false
  return {
    'GET /api/v1/auth/me': () => (signedIn ? { body: ME_SALES } : unauthenticated),
    'POST /api/v1/auth/login': () => {
      signedIn = true
      return { body: ME_SALES }
    },
  }
}

describe('LoginPage directory login (UI-1)', () => {
  it('shows the AD id and password form', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': authConfig() })

    renderApp(tree, '/login')

    expect(await screen.findByLabelText('AD 아이디')).toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: '로그인' })).toBeInTheDocument()
    expect(screen.queryByText('개발용 로그인')).not.toBeInTheDocument()
  })

  it('posts the credentials with the CSRF header and moves to the main page', async () => {
    const requests = mockApi({
      ...sessionAfterLogin(),
      'GET /api/v1/auth/config': authConfig(),
    })
    renderApp(tree, '/login')

    await submit('kim', 'pw-1')

    expect(await screen.findByText('메인 화면')).toBeInTheDocument()
    const login = requests.find((r) => r.path === '/api/v1/auth/login')
    expect(login?.method).toBe('POST')
    expect(login?.body).toEqual({ login_id: 'kim', password: 'pw-1' })
    expect(login?.headers.get('x-requested-with')).toBe('neoine-web')
  })

  it('shows the fixed failure message and clears only the password', async () => {
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': authConfig(),
      'POST /api/v1/auth/login': problem(401, 'unauthenticated', FIXED),
    })
    renderApp(tree, '/login')

    await submit('kim', 'wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent(FIXED)
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('kim')
    expect(screen.queryByText(/unauthenticated/)).not.toBeInTheDocument()
  })

  it('explains that too many attempts were made on 429', async () => {
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': authConfig(),
      'POST /api/v1/auth/login': problem(429, 'too-many-attempts', '잠금'),
    })
    renderApp(tree, '/login')

    await submit()

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
  })

  it('explains that the AD server is unreachable on 503', async () => {
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': authConfig(),
      'POST /api/v1/auth/login': problem(503, 'directory-unavailable', '일시 장애'),
    })
    renderApp(tree, '/login')

    await submit()

    expect(await screen.findByRole('alert')).toHaveTextContent('AD 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.')
  })

  it('goes to the main page when already signed in', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME_SALES }, 'GET /api/v1/auth/config': authConfig() })

    renderApp(tree, '/login')

    expect(await screen.findByText('메인 화면')).toBeInTheDocument()
  })
})

describe('LoginPage setup guidance (UI-2)', () => {
  it.each([
    ['needs_directory_setup', { directory_login: false, needs_directory_setup: true }],
    ['needs_admin_setup', { needs_admin_setup: true }],
    ['a missing AD registration', { directory_login: false }],
  ])('redirects to setup for %s', async (_name, flags) => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': authConfig(flags) })

    renderApp(tree, '/login')

    expect(await screen.findByText('최초 설정 화면')).toBeInTheDocument()
  })
})

describe('LoginPage dev login (UI-2, UI-11)', () => {
  it('offers admin, sales and user roles and signs in with the chosen one', async () => {
    const requests = mockApi({
      ...sessionAfterLogin(),
      'GET /api/v1/auth/config': authConfig({ dev_login: true }),
      'POST /api/v1/auth/dev-login': { body: ME_SALES },
    })
    renderApp(tree, '/login')

    const select = await screen.findByLabelText('역할')
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.value)
    expect(options.sort()).toEqual(['admin', 'sales', 'user'])
    await userEvent.selectOptions(select, 'user')
    await userEvent.click(screen.getByRole('button', { name: '개발용으로 로그인' }))

    await waitFor(() => expect(requests.some((r) => r.path === '/api/v1/auth/dev-login')).toBe(true))
    const login = requests.find((r) => r.path === '/api/v1/auth/dev-login')
    expect(login?.body).toEqual({ role: 'user' })
    expect(login?.headers.get('x-requested-with')).toBe('neoine-web')
  })

  it('hides the dev login when the server does not enable it', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': authConfig() })

    renderApp(tree, '/login')

    await screen.findByLabelText('AD 아이디')
    expect(screen.queryByText('개발용 로그인')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('역할')).not.toBeInTheDocument()
  })

  it('shows the dev login next to the AD form when both are available', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': authConfig({ dev_login: true }) })

    renderApp(tree, '/login')

    expect(await screen.findByText('개발용 로그인')).toBeInTheDocument()
    expect(screen.getByLabelText('AD 아이디')).toBeInTheDocument()
  })
})

describe('LoginPage without company SSO (UI-5)', () => {
  it('has no company SSO link and ignores the old error query', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': authConfig() })

    renderApp(tree, '/login?error=denied')

    await screen.findByLabelText('AD 아이디')
    expect(screen.queryByRole('link', { name: /회사 계정/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
