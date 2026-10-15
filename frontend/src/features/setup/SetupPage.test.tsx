import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway, mockControl } from '../../gateway'
import { fillDirectoryForm, setField } from '../../test/directoryForm'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 게이트웨이가 실제로 던지는 ApiError 하나(로그아웃 상태의 me() → 401). */
async function serverError(): Promise<unknown> {
  await gateway.auth.logout()
  return gateway.auth.me().catch((e: unknown) => e)
}

type Rendered = Awaited<ReturnType<typeof renderAt>>

/** 최초 설정이 아직 안 된 상태(MockPanel의 "최초 설정 다시 시작"과 같다)로 /setup을 연다. */
async function openSetup() {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  const view = await renderAt('/setup', { role: null })
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  return view
}

async function saveStepOne(user: Rendered['user']) {
  fillDirectoryForm()
  await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
  await screen.findByRole('heading', { name: '파일 저장 위치' })
}

async function saveStepTwo(user: Rendered['user'], path = '/data/neoine-sales/files') {
  await user.type(screen.getByLabelText('저장 경로'), path)
  await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))
  await screen.findByRole('heading', { name: '관리자 등록' })
}

async function registerAdmin(user: Rendered['user'], loginId: string, password: string) {
  if (loginId) await user.type(screen.getByLabelText('AD 아이디'), loginId)
  if (password) await user.type(screen.getByLabelText('비밀번호'), password)
  await user.click(screen.getByRole('button', { name: '관리자 등록' }))
}

function steps() {
  return within(screen.getByRole('list', { name: '설정 단계' }))
}

describe('최초 설정 1단계: AD 서버 (T-SETUP-01)', () => {
  it('opens at the AD server registration with the documented defaults', async () => {
    await openSetup()

    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue('(&(objectClass=user)(sAMAccountName={login_id}))')
    expect(screen.getByLabelText(/표시 이름 속성/)).toHaveValue('displayName')
    expect(screen.getByLabelText(/이메일 속성/)).toHaveValue('mail')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.getByLabelText(/응답 제한 시간/)).toHaveValue(10)
    expect(screen.getByLabelText(/StartTLS/)).toHaveAttribute('type', 'checkbox')
    expect(screen.getByLabelText(/CA 인증서/)).toBeInTheDocument()
  })

  it('shows the three steps with the first one current, and no later step content', async () => {
    await openSetup()

    expect(steps().getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '1. AD 서버 등록',
      '2. 파일 저장 위치',
      '3. 관리자 등록',
    ])
    expect(steps().getByText('1. AD 서버 등록').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(screen.queryByLabelText('저장 경로')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('AD 아이디')).not.toBeInTheDocument()
  })

  it('does not draw its own mock badge (the app banner does)', async () => {
    await openSetup()

    expect(screen.getAllByText(/UI 목업\(메모리 저장\)/)).toHaveLength(1)
  })

  it('saves the directory settings as one URL per line and moves to step 2', async () => {
    const { user } = await openSetup()
    const save = vi.spyOn(gateway.setup, 'saveDirectory')
    fillDirectoryForm()
    const starttls = screen.getByLabelText(/StartTLS/) as HTMLInputElement
    const before = starttls.checked
    await user.click(starttls)

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect(save).toHaveBeenCalledWith({
      serverUrls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test:6636'],
      useStarttls: !before,
      caCertPem: null,
      bindTemplate: 'CORP\\{login_id}',
      baseDn: 'dc=corp,dc=test',
      userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))',
      displayNameAttribute: 'displayName',
      emailAttribute: 'mail',
      connectTimeoutSeconds: 5,
      receiveTimeoutSeconds: 10,
    })
    expect(steps().getByText('1. AD 서버 등록').closest('li')).toHaveTextContent('완료')
    expect(steps().getByText('2. 파일 저장 위치').closest('li')).toHaveAttribute('aria-current', 'step')
  })

  it('sends the pasted CA certificate', async () => {
    const { user } = await openSetup()
    const save = vi.spyOn(gateway.setup, 'saveDirectory')
    fillDirectoryForm()
    setField(/CA 인증서/, '-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----')

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    await screen.findByRole('heading', { name: '파일 저장 위치' })
    expect(save.mock.calls[0]?.[0].caCertPem).toBe('-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----')
  })

  it('shows the server message for an invalid value, keeps the input and stays on step 1', async () => {
    const { user } = await openSetup()
    fillDirectoryForm({ baseDn: '' })

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Base DN을 입력하세요.')
    expect(screen.getByLabelText(/서버 URL/)).toHaveValue('ldaps://dc1.corp.test\nldaps://dc2.corp.test:6636')
    expect(screen.getByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
  })
})

describe('최초 설정 2단계: 파일 저장 위치 (T-SETUP-02)', () => {
  it('opens only after step 1 and explains the location', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)

    expect(screen.getByLabelText('저장 경로')).toHaveValue('')
    expect(screen.getByText(/위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/서버 URL/)).not.toBeInTheDocument()
  })

  it('rejects a relative path and stays on step 2', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)

    await user.type(screen.getByLabelText('저장 경로'), 'data/files')
    await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
    expect(screen.getByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
  })

  it('reports an unwritable location without moving on and keeps the input', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)

    await user.type(screen.getByLabelText('저장 경로'), '/readonly/files')
    await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('해당 위치에 쓸 수 없습니다.')
    expect(screen.getByLabelText('저장 경로')).toHaveValue('/readonly/files')
    expect(screen.getByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
  })

  it('refuses an empty path with the server message', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)

    await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('절대 경로를 입력하세요.')
  })

  it('goes back to step 1 and registers the AD server again', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)

    await user.click(screen.getByRole('button', { name: 'AD 서버 다시 등록' }))

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    fillDirectoryForm({ baseDn: 'dc=other,dc=test' })
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
  })
})

describe('최초 설정 3단계: 관리자 등록 (T-SETUP-03)', () => {
  it('shows the first-admin notice with id and password fields', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)
    await saveStepTwo(user)

    expect(screen.getByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).toBeInTheDocument()
    expect(screen.getByLabelText('AD 아이디')).toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
  })

  it('shows the message when id or password is missing and stays on step 3', async () => {
    const { user } = await openSetup()
    await saveStepOne(user)
    await saveStepTwo(user)

    await registerAdmin(user, 'boss', '')

    expect(await screen.findByRole('alert')).toHaveTextContent('아이디와 비밀번호를 입력하세요.')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('boss')
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  it('signs in as the new admin and moves to the main page', async () => {
    const { user, location } = await openSetup()
    await saveStepOne(user)
    await saveStepTwo(user)

    await registerAdmin(user, 'boss', 'secret')

    await waitFor(() => expect(location()).toBe('/deals'))
    expect(await screen.findByRole('link', { name: 'Admin' })).toBeInTheDocument()
    expect(screen.getByText('boss (admin)')).toBeInTheDocument()
  })

  it('promotes an existing active user to admin when the id matches', async () => {
    const { user, location } = await openSetup()
    await saveStepOne(user)
    await saveStepTwo(user)

    await registerAdmin(user, 'kim', 'secret')

    await waitFor(() => expect(location()).toBe('/deals'))
    expect(await screen.findByText('김영업 (admin)')).toBeInTheDocument()
  })

  it('does not keep the typed password on screen after a failure', async () => {
    const error = await serverError()
    const { user } = await openSetup()
    await saveStepOne(user)
    await saveStepTwo(user)
    vi.spyOn(gateway.setup, 'registerAdmin').mockRejectedValue(error)

    await registerAdmin(user, 'boss', 'secret')

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
  })
})

describe('최초 설정 진입 규칙 (T-SETUP-04~05)', () => {
  it('goes to the login page when everything is already configured', async () => {
    const { location } = await renderAt('/setup', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
  })

  it('goes to the login page for a signed-in admin too', async () => {
    const { location } = await renderAt('/setup', { role: 'admin' })

    await waitFor(() => expect(location()).not.toBe('/setup'))
  })

  it('starts over from the mock menu: step 1 again, signed out', async () => {
    const { user, location } = await renderAt('/deals', { role: 'admin' })
    await screen.findByRole('link', { name: 'Admin' })

    await user.click(screen.getByRole('button', { name: '목업 메뉴' }))
    await user.click(screen.getByRole('button', { name: '최초 설정 다시 시작' }))

    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    expect(location()).toBe('/setup')
  })

  it('shows the message when the setup status cannot be loaded', async () => {
    vi.spyOn(gateway.setup, 'status').mockRejectedValue(await serverError())
    await renderAt('/setup', { role: null })

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  })
})
