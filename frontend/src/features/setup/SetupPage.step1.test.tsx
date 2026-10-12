import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import { authConfig, DIRECTORY_SETTINGS } from '../../test/authFixtures'
import { fillDirectoryForm, setField } from '../../test/directoryForm'
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

describe('SetupPage step 1 (UI-3)', () => {
  it('opens at the AD server registration with the documented defaults', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': NEEDS_DIRECTORY })

    renderApp(tree, '/setup')

    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue('(&(objectClass=user)(sAMAccountName={login_id}))')
    expect(screen.getByLabelText(/표시 이름 속성/)).toHaveValue('displayName')
    expect(screen.getByLabelText(/이메일 속성/)).toHaveValue('mail')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.getByLabelText(/응답 제한 시간/)).toHaveValue(10)
    expect(screen.getByLabelText(/StartTLS/)).toHaveAttribute('type', 'checkbox')
    expect(screen.getByLabelText(/CA 인증서/)).toBeInTheDocument()
  })

  it('does not show the admin step before the AD server is registered', async () => {
    mockApi({ 'GET /api/v1/auth/me': unauthenticated, 'GET /api/v1/auth/config': NEEDS_DIRECTORY })

    renderApp(tree, '/setup')

    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    expect(screen.queryByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('AD 아이디')).not.toBeInTheDocument()
  })

  it('saves the directory settings as one URL per line and moves to step 2', async () => {
    const requests = mockApi(wizardRoutes())
    renderApp(tree, '/setup')
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm({ urls: ' ldaps://dc1.corp.test \n\nldaps://dc2.corp.test:6636\n' })
    const starttls = screen.getByLabelText(/StartTLS/) as HTMLInputElement
    const before = starttls.checked
    await userEvent.click(starttls)

    await userEvent.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).toBeInTheDocument()
    const put = requests.find((r) => r.method === 'PUT')
    expect(put?.path).toBe('/api/v1/auth/setup/directory')
    expect(put?.headers.get('x-requested-with')).toBe('neoine-web')
    expect(put?.body).toEqual({
      server_urls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test:6636'],
      use_starttls: !before,
      ca_cert_pem: null,
      bind_template: 'CORP\\{login_id}',
      base_dn: 'dc=corp,dc=test',
      user_filter: '(&(objectClass=user)(sAMAccountName={login_id}))',
      display_name_attribute: 'displayName',
      email_attribute: 'mail',
      connect_timeout_seconds: 5,
      receive_timeout_seconds: 10,
    })
  })

  it('sends the pasted CA certificate', async () => {
    const requests = mockApi(wizardRoutes())
    renderApp(tree, '/setup')
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm()
    setField(/CA 인증서/, '-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----')

    await userEvent.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    await screen.findByText('처음 등록하는 AD 계정이 관리자가 됩니다.')
    const put = requests.find((r) => r.method === 'PUT')
    expect(put?.body).toMatchObject({ ca_cert_pem: '-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----' })
  })

  it.each([
    ['connect', 'AD 서버에 연결할 수 없습니다'],
    ['tls', 'TLS 연결을 확인하지 못했습니다'],
    ['bind', '바인드 템플릿'],
    ['search', '사용자 검색에 실패했습니다'],
  ])('explains the %s stage when the verification fails', async (stage, text) => {
    mockApi(
      wizardRoutes({
        'PUT /api/v1/auth/setup/directory': problem(422, 'directory-verification-failed', 'AD 설정을 확인하지 못했습니다', { stage }),
      }),
    )
    renderApp(tree, '/setup')

    await saveStepOne()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(text)
    expect(alert).not.toHaveTextContent('directory-verification-failed')
    expect(screen.getByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    expect(screen.getByLabelText(/Base DN/)).toHaveValue('dc=corp,dc=test')
  })

  it('shows the server message for an invalid value and stays on step 1', async () => {
    mockApi(wizardRoutes({ 'PUT /api/v1/auth/setup/directory': problem(422, 'invalid-value', '서버 URL은 ldaps:// 형식이어야 합니다') }))
    renderApp(tree, '/setup')

    await saveStepOne()

    expect(await screen.findByRole('alert')).toHaveTextContent('서버 URL은 ldaps:// 형식이어야 합니다')
    expect(screen.queryByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).not.toBeInTheDocument()
  })

  it('goes to the login page when an admin already exists (409)', async () => {
    let closed = false
    mockApi(
      wizardRoutes({
        'GET /api/v1/auth/config': () => (closed ? DONE : NEEDS_DIRECTORY),
        'PUT /api/v1/auth/setup/directory': () => {
          closed = true
          return problem(409, 'invalid-state', '이미 관리자가 등록되어 있습니다')
        },
      }),
    )
    renderApp(tree, '/setup')

    await saveStepOne()

    expect(await screen.findByText('로그인 화면')).toBeInTheDocument()
  })
})
