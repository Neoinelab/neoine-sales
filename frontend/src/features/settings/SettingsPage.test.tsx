import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { formatDateTime } from '../../shared/format'
import { DIRECTORY_SETTINGS, ME_ADMIN, ME_DEV_ADMIN, userRef } from '../../test/authFixtures'
import { setField } from '../../test/directoryForm'
import { mockApi, problem, renderApp } from '../../test/utils'
import { SettingsPage } from './SettingsPage'

const GET = 'GET /api/v1/settings/directory'
const PUT = 'PUT /api/v1/settings/directory'
const TEST = 'POST /api/v1/settings/directory/test'
const NEW_DN = 'dc=new,dc=test'

async function openPage(routes: Parameters<typeof mockApi>[0], me = ME_ADMIN) {
  const requests = mockApi({ 'GET /api/v1/auth/me': { body: me }, [GET]: { body: DIRECTORY_SETTINGS }, ...routes })
  renderApp(<SettingsPage />)
  await waitFor(() => expect(screen.getByLabelText(/Base DN/)).toHaveValue('dc=corp,dc=test'))
  return requests
}

const typePassword = (value: string) => userEvent.type(screen.getByLabelText(/현재 관리자 비밀번호/), value)

describe('SettingsPage current settings (UI-8)', () => {
  it('shows the saved settings in the edit form', async () => {
    await openPage({})

    expect(screen.getByLabelText(/서버 URL/)).toHaveValue('ldaps://dc1.corp.test\nldaps://dc2.corp.test')
    expect(screen.getByLabelText(/바인드 템플릿/)).toHaveValue('CORP\\{login_id}')
    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue(DIRECTORY_SETTINGS.user_filter)
    expect(screen.getByLabelText(/표시 이름 속성/)).toHaveValue('displayName')
    expect(screen.getByLabelText(/이메일 속성/)).toHaveValue('mail')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.getByLabelText(/응답 제한 시간/)).toHaveValue(10)
    expect(screen.getByRole('heading', { name: 'AD 서버 설정' })).toBeInTheDocument()
  })

  it('shows who changed the settings last and when', async () => {
    await openPage({})

    const line = screen.getByText(formatDateTime(DIRECTORY_SETTINGS.updated_at), { exact: false })
    expect(line).toHaveTextContent('최관리')
  })

  it('shows a resigned last editor with the 이름(퇴사) label', async () => {
    await openPage({ [GET]: { body: { ...DIRECTORY_SETTINGS, updated_by: userRef('u-7', '이퇴사', true) } } })
    expect(screen.getByText(formatDateTime(DIRECTORY_SETTINGS.updated_at), { exact: false })).toHaveTextContent('이퇴사(퇴사)')
  })

  it('asks for the current admin password to confirm the new settings', async () => {
    await openPage({})

    const password = screen.getByLabelText(/현재 관리자 비밀번호/)
    expect(password).toHaveAttribute('type', 'password')
    expect(password).toBeRequired()
  })

  it('shows the server message when the settings cannot be loaded', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, [GET]: problem(404, 'not-found', 'AD 서버 설정이 없습니다') })

    renderApp(<SettingsPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('AD 서버 설정이 없습니다')
  })
})

describe('SettingsPage connection test (UI-8)', () => {
  it('tests the form values with the admin password without saving', async () => {
    const requests = await openPage({
      [TEST]: { body: { success: true, stage: null, message: 'AD 서버 연결을 확인했습니다' } },
    })
    setField(/Base DN/, NEW_DN)
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '연결 테스트' }))

    expect(await screen.findByRole('status')).toHaveTextContent('AD 서버 연결을 확인했습니다')
    const post = requests.find((r) => r.method === 'POST' && r.path === '/api/v1/settings/directory/test')
    expect(post?.body).toMatchObject({
      server_urls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
      base_dn: NEW_DN,
      bind_template: 'CORP\\{login_id}',
      password: 'pw-root',
    })
    expect(post?.body).not.toHaveProperty('expected_revision')
    expect(requests.some((r) => r.method === 'PUT')).toBe(false)
  })

  it.each([
    ['connect', 'AD 서버에 연결할 수 없습니다'],
    ['tls', 'TLS 연결을 확인하지 못했습니다'],
    ['bind', '바인드 템플릿'],
    ['search', '사용자 검색에 실패했습니다'],
  ])('shows the failed %s stage with the server message', async (stage, text) => {
    await openPage({ [TEST]: { body: { success: false, stage, message: '서버가 거절했습니다' } } })
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '연결 테스트' }))

    const result = await screen.findByRole('status')
    expect(result).toHaveTextContent(text)
    expect(result).toHaveTextContent('서버가 거절했습니다')
  })

  it('clears the password once the test request ends', async () => {
    await openPage({ [TEST]: { body: { success: true, stage: null, message: '확인' } } })
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '연결 테스트' }))

    await screen.findByRole('status')
    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).toHaveValue('')
  })
})

describe('SettingsPage save (UI-8)', () => {
  it('saves with the expected revision and password, then clears the password', async () => {
    const requests = await openPage({
      [PUT]: { body: { ...DIRECTORY_SETTINGS, base_dn: NEW_DN, revision: 4 } },
    })
    setField(/Base DN/, NEW_DN)
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('status')).toHaveTextContent('저장했습니다')
    const put = requests.find((r) => r.method === 'PUT')
    expect(put?.path).toBe('/api/v1/settings/directory')
    expect(put?.headers.get('x-requested-with')).toBe('neoine-web')
    expect(put?.body).toEqual({
      server_urls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
      use_starttls: false,
      ca_cert_pem: null,
      bind_template: 'CORP\\{login_id}',
      base_dn: NEW_DN,
      user_filter: DIRECTORY_SETTINGS.user_filter,
      display_name_attribute: 'displayName',
      email_attribute: 'mail',
      connect_timeout_seconds: 5,
      receive_timeout_seconds: 10,
      expected_revision: 3,
      password: 'pw-root',
    })
    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).toHaveValue('')
  })

  it('uses the new revision for the next save', async () => {
    const requests = await openPage({ [PUT]: { body: { ...DIRECTORY_SETTINGS, revision: 4 } } })
    await typePassword('pw-1')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))
    await screen.findByRole('status')

    await typePassword('pw-2')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(requests.filter((r) => r.method === 'PUT')).toHaveLength(2))
    const puts = requests.filter((r) => r.method === 'PUT')
    expect(puts.map((r) => (r.body as { expected_revision: number }).expected_revision)).toEqual([3, 4])
  })

  it('explains the conflict and asks to reload on a stale revision (409)', async () => {
    await openPage({ [PUT]: problem(409, 'invalid-state', 'revision mismatch') })
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('다른 곳에서 설정이 변경되었습니다. 새로고침한 뒤 다시 시도하세요.')
    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).toHaveValue('')
  })

  it.each([
    ['connect', 'AD 서버에 연결할 수 없습니다'],
    ['tls', 'TLS 연결을 확인하지 못했습니다'],
    ['bind', '바인드 템플릿'],
    ['search', '사용자 검색에 실패했습니다'],
  ])('explains the %s stage when the verification fails (422)', async (stage, text) => {
    await openPage({
      [PUT]: problem(422, 'directory-verification-failed', '설정을 확인하지 못했습니다', { stage }),
    })
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(text)
    expect(alert).not.toHaveTextContent('directory-verification-failed')
    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).toHaveValue('')
  })

  it('explains too many attempts (429)', async () => {
    await openPage({ [PUT]: problem(429, 'too-many-attempts', '잠금') })
    await typePassword('pw-root')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('시도가 너무 많습니다. 잠시 후 다시 시도하세요.')
    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).toHaveValue('')
  })
})

describe('SettingsPage as the dev admin (UI-8)', () => {
  it('lets the dev admin save without a password', async () => {
    const requests = await openPage({ [PUT]: { body: { ...DIRECTORY_SETTINGS, revision: 4 } } }, ME_DEV_ADMIN)
    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).not.toBeRequired()

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('status')).toHaveTextContent('저장했습니다')
    const put = requests.find((r) => r.method === 'PUT')
    expect((put?.body as { password?: string | null }).password ?? null).toBeNull()
    expect(put?.body).toMatchObject({ expected_revision: 3 })
  })

  it('still asks for a password when the subject only looks like the old dev: prefix', async () => {
    await openPage({}, { ...ME_ADMIN, subject: 'dev:admin' })

    expect(screen.getByLabelText(/현재 관리자 비밀번호/)).toBeRequired()
  })

  it('does not send a save request without a password for a directory admin', async () => {
    const requests = await openPage({ [PUT]: { body: DIRECTORY_SETTINGS } })

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(requests.some((r) => r.method === 'PUT')).toBe(false)
  })
})
