import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { authConfig, DIRECTORY_SETTINGS, ME_ADMIN } from '../../test/authFixtures'
import { fillDirectoryForm } from '../../test/directoryForm'
import { mockApi, problem, renderApp } from '../../test/utils'
import { SetupPage } from './SetupPage'

const unauthenticated = problem(401, 'unauthenticated', '로그인이 필요합니다')
const NEEDS_DIRECTORY = authConfig({ directory_login: false, needs_directory_setup: true })
const NEEDS_ADMIN = authConfig({ needs_admin_setup: true })
const DONE = authConfig()

const tree = (
  <Routes>
    <Route path="/setup" element={<SetupPage />} />
    <Route path="/login" element={<p>로그인 화면</p>} />
    <Route path="/" element={<p>메인 화면</p>} />
  </Routes>
)

/** 1단계 저장 전에는 AD 미등록, 저장한 뒤에는 관리자 등록 대기로 바뀌는 config. */
function wizardRoutes(extra: Record<string, unknown> = {}) {
  let saved = false
  return {
    'GET /api/v1/auth/me': unauthenticated,
    'GET /api/v1/auth/config': () => (saved ? NEEDS_ADMIN : NEEDS_DIRECTORY),
    'PUT /api/v1/auth/setup/directory': () => {
      saved = true
      return { body: { ...DIRECTORY_SETTINGS, revision: 1, updated_by: null } }
    },
    ...extra,
  } as Parameters<typeof mockApi>[0]
}

async function saveStepOne() {
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  fillDirectoryForm()
  await userEvent.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
}

describe('SetupPage step 2 (UI-4)', () => {
  it('shows the first-admin notice with id and password fields', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': NEEDS_ADMIN })

    renderApp(tree, '/setup')

    expect(await screen.findByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).toBeInTheDocument()
    expect(screen.getByLabelText('AD 아이디')).toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
    expect(screen.getByRole('button', { name: '관리자 등록' })).toBeInTheDocument()
    expect(screen.queryByLabelText(/Base DN/)).not.toBeInTheDocument()
  })

  it('signs in as the new admin and moves to the main page', async () => {
    let signedIn = false
    const requests = mockApi({
      'GET /api/v1/auth/me': () => (signedIn ? { body: ME_ADMIN } : unauthenticated),
      'GET /api/v1/auth/config': () => (signedIn ? DONE : NEEDS_ADMIN),
      'POST /api/v1/auth/setup': () => {
        signedIn = true
        return { body: ME_ADMIN }
      },
    })
    renderApp(tree, '/setup')
    await userEvent.type(await screen.findByLabelText('AD 아이디'), 'root')
    await userEvent.type(screen.getByLabelText('비밀번호'), 'pw-root')

    await userEvent.click(screen.getByRole('button', { name: '관리자 등록' }))

    expect(await screen.findByText('메인 화면')).toBeInTheDocument()
    const post = requests.find((r) => r.method === 'POST' && r.path === '/api/v1/auth/setup')
    expect(post?.body).toEqual({ login_id: 'root', password: 'pw-root' })
    expect(post?.headers.get('x-requested-with')).toBe('neoine-web')
  })

  it('shows the failure and clears the password when the AD login fails', async () => {
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': NEEDS_ADMIN,
      'POST /api/v1/auth/setup': problem(401, 'unauthenticated', '아이디 또는 비밀번호가 올바르지 않습니다'),
    })
    renderApp(tree, '/setup')
    await userEvent.type(await screen.findByLabelText('AD 아이디'), 'root')
    await userEvent.type(screen.getByLabelText('비밀번호'), 'wrong')

    await userEvent.click(screen.getByRole('button', { name: '관리자 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('아이디 또는 비밀번호가 올바르지 않습니다')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('root')
  })

  it.each([
    [429, 'too-many-attempts', '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.'],
    [503, 'directory-unavailable', 'AD 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.'],
  ])('explains %s while registering the admin', async (status, kind, text) => {
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': NEEDS_ADMIN,
      'POST /api/v1/auth/setup': problem(status, kind, 'x'),
    })
    renderApp(tree, '/setup')
    await userEvent.type(await screen.findByLabelText('AD 아이디'), 'root')
    await userEvent.type(screen.getByLabelText('비밀번호'), 'pw')

    await userEvent.click(screen.getByRole('button', { name: '관리자 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(text)
  })

  it('goes back to step 1 and registers the AD server again', async () => {
    const requests = mockApi(wizardRoutes())
    renderApp(tree, '/setup')
    await saveStepOne()
    await screen.findByText('처음 등록하는 AD 계정이 관리자가 됩니다.')

    await userEvent.click(screen.getByRole('button', { name: 'AD 서버 다시 등록' }))

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    expect(screen.queryByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).not.toBeInTheDocument()
    fillDirectoryForm({ baseDn: 'dc=other,dc=test' })
    await userEvent.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByText('처음 등록하는 AD 계정이 관리자가 됩니다.')
    const puts = requests.filter((r) => r.method === 'PUT')
    expect(puts).toHaveLength(2)
    expect(puts[1]?.body).toMatchObject({ base_dn: 'dc=other,dc=test' })
  })

  it('goes to the login page when an admin already exists (409)', async () => {
    let closed = false
    mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': () => (closed ? DONE : NEEDS_ADMIN),
      'POST /api/v1/auth/setup': () => {
        closed = true
        return problem(409, 'invalid-state', '이미 관리자가 등록되어 있습니다')
      },
    })
    renderApp(tree, '/setup')
    await userEvent.type(await screen.findByLabelText('AD 아이디'), 'root')
    await userEvent.type(screen.getByLabelText('비밀번호'), 'pw')

    await userEvent.click(screen.getByRole('button', { name: '관리자 등록' }))

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
  })
})

describe('SetupPage guards', () => {
  it('shows no setup screen when everything is already configured', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': DONE })

    renderApp(tree, '/setup')

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
  })

  it('offers the dev login on the wizard too, including the user role', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': unauthenticated,
      'GET /api/v1/auth/config': authConfig({ dev_login: true, directory_login: false, needs_directory_setup: true }),
      'POST /api/v1/auth/dev-login': { body: ME_ADMIN },
    })
    renderApp(tree, '/setup')

    const select = await screen.findByLabelText('역할')
    expect(Array.from(select.querySelectorAll('option')).map((o) => o.value).sort()).toEqual(['admin', 'sales', 'user'])
    await userEvent.selectOptions(select, 'admin')
    await userEvent.click(screen.getByRole('button', { name: '개발용으로 로그인' }))

    await waitFor(() => expect(requests.some((r) => r.path === '/api/v1/auth/dev-login')).toBe(true))
    expect(requests.find((r) => r.path === '/api/v1/auth/dev-login')?.body).toEqual({ role: 'admin' })
  })

  it('hides the dev login when the server does not enable it', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': NEEDS_DIRECTORY })

    renderApp(tree, '/setup')

    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    expect(screen.queryByText('개발용 로그인')).not.toBeInTheDocument()
  })
})
