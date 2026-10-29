import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { DirectorySettings } from '../model/types'
import { DIRECTORY_SAVED } from '../../test/directoryFixtures'
import { fillDirectoryForm, selectSecurity, setField } from '../../test/directoryForm'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { BIND_PASSWORD_MASK } from './directoryForm'

/**
 * AD 입력 칸 묶음(최초 설정 1단계와 Admin > 외부연동 AD 설정이 함께 쓴다)의 화면 규칙.
 * AC1(칸 7개), AC4(비밀번호 마스크·재입력), AC8(보안 연결 기본 포트·경고 문구), AC10(읽을 수 없음).
 * 두 화면을 실제로 렌더해 확인한다(칸 묶음은 화면이 상태를 쥐고 있다).
 */

afterEach(() => vi.restoreAllMocks())

const RETYPE_NOTICE = '서버나 바인드 계정을 바꿨으므로 비밀번호를 다시 입력하세요'
const UNREADABLE_NOTICE = '저장된 바인드 비밀번호를 읽을 수 없습니다. 다시 입력하세요'
const KEEP_HINT = '그대로 두면 저장된 비밀번호를 씁니다'
const PLAIN_WARNING = '비밀번호가 암호화되지 않은 채 전송됩니다'
const NO_VERIFY_WARNING = '서버 인증서를 검증하지 않습니다'
const REMOVED_LABELS = [/서버 URL/, /StartTLS 사용/, /CA 인증서/, /바인드 템플릿/, /^Base DN/, /표시 이름 속성/, /이메일 속성/, /응답 제한 시간/]

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openSetup(): Promise<Rendered> {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  const view = await renderAt('/setup', { role: null })
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  return view
}

async function openSettings(saved: DirectorySettings | null = DIRECTORY_SAVED): Promise<Rendered> {
  vi.spyOn(gateway.settings, 'getDirectory').mockResolvedValue(saved)
  const view = await renderAt('/admin/integrations', { role: 'admin' })
  await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
  await screen.findByLabelText(/^호스트/)
  return view
}

const directory = () => within(screen.getByRole('region', { name: 'AD(LDAP) 서버 설정' }))
const password = () => screen.getByLabelText(/^바인드 비밀번호/)

describe('입력 칸 7개 (AC1, 최초 설정)', () => {
  it('has exactly the seven inputs: host, port, security, bind account, bind password, user filter, connect timeout', async () => {
    await openSetup()
    const form = screen.getByRole('heading', { name: 'AD 서버 등록' }).closest('form') as HTMLFormElement

    for (const label of [/^호스트/, /^포트/, /^보안 연결/, /^바인드 계정/, /^바인드 비밀번호/, /사용자 검색 필터/, /연결 제한 시간/]) {
      expect(within(form).getByLabelText(label)).toBeInTheDocument()
    }
    expect(form.querySelectorAll('input, select, textarea')).toHaveLength(7)
  })

  it('has none of the removed inputs', async () => {
    await openSetup()

    for (const label of REMOVED_LABELS) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  it('opens with SSL on 636, the default filter, a 5 second timeout and an empty password', async () => {
    await openSetup()

    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue('(&(objectClass=user)(sAMAccountName={login_id}))')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.getByLabelText(/^호스트/)).toHaveValue('')
    expect(password()).toHaveValue('')
  })

  it('offers none, SSL and StartTLS for the security mode', async () => {
    await openSetup()

    const options = within(screen.getByLabelText(/^보안 연결/)).getAllByRole('option')
    expect(options.map((o) => [(o as HTMLOptionElement).value, o.textContent])).toEqual([
      ['none', '없음'],
      ['ssl', 'SSL'],
      ['starttls', 'StartTLS'],
    ])
  })

  it('keeps the bind password out of autofill and masks it', async () => {
    await openSetup()

    expect(password()).toHaveAttribute('type', 'password')
    expect(password()).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.getByLabelText(/^호스트/)).toHaveAttribute('autocomplete', 'off')
  })

  it('does not show the stored-password hint when registering for the first time', async () => {
    await openSetup()

    expect(screen.queryByText(KEEP_HINT, { exact: false })).not.toBeInTheDocument()
  })
})

describe('보안 연결 방식과 포트 (AC8)', () => {
  it('switches to the default port of the chosen mode', async () => {
    const { user } = await openSetup()

    await selectSecurity(user, 'none')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(389)
    await selectSecurity(user, 'starttls')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(389)
    await selectSecurity(user, 'ssl')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
  })

  it('fills the default port when the port field was emptied', async () => {
    const { user } = await openSetup()
    setField(/^포트/, '')

    await selectSecurity(user, 'none')

    expect(screen.getByLabelText(/^포트/)).toHaveValue(389)
  })

  it('keeps a port the user typed when the mode changes', async () => {
    const { user } = await openSetup()
    setField(/^포트/, '3269')

    await selectSecurity(user, 'starttls')

    expect(screen.getByLabelText(/^포트/)).toHaveValue(3269)
  })

  it('warns that nothing is encrypted for the none mode only', async () => {
    const { user } = await openSetup()

    await selectSecurity(user, 'none')

    expect(screen.getByText(PLAIN_WARNING, { exact: false })).toBeInTheDocument()
    expect(screen.queryByText(NO_VERIFY_WARNING, { exact: false })).not.toBeInTheDocument()
  })

  it.each(['ssl', 'starttls'] as const)('warns that the server certificate is not verified for %s', async (mode) => {
    const { user } = await openSetup()

    await selectSecurity(user, 'none')
    await selectSecurity(user, mode)

    expect(screen.getByText(NO_VERIFY_WARNING, { exact: false })).toBeInTheDocument()
    expect(screen.queryByText(PLAIN_WARNING, { exact: false })).not.toBeInTheDocument()
  })
})

describe('최초 설정에서는 바인드 비밀번호가 필수다 (AC4)', () => {
  it('asks for the bind password before sending anything', async () => {
    const { user } = await openSetup()
    const save = vi.spyOn(gateway.setup, 'saveDirectory')
    fillDirectoryForm({ bindPassword: '' })

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(save).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
  })

  it('sends the seven values with the typed password', async () => {
    const { user } = await openSetup()
    const save = vi.spyOn(gateway.setup, 'saveDirectory')
    fillDirectoryForm({ host: 'dc2.corp.test', bindAccount: 'svc@corp.test', bindPassword: 'Typed-pw-3!' })
    await selectSecurity(user, 'starttls')

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    await screen.findByRole('heading', { name: '파일 저장 위치' })
    expect(save).toHaveBeenCalledWith({
      host: 'dc2.corp.test',
      port: 389,
      security: 'starttls',
      bindAccount: 'svc@corp.test',
      bindPassword: 'Typed-pw-3!',
      userFilter: '(&(objectClass=user)(sAMAccountName={login_id}))',
      connectTimeoutSeconds: 5,
    })
  })

  it('explains the failed stage and keeps the other inputs after a failed registration', async () => {
    const { user } = await openSetup()
    vi.spyOn(gateway.setup, 'saveDirectory').mockRejectedValue(await failure('service_bind'))
    fillDirectoryForm()

    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('바인드 계정으로 AD에 로그인하지 못했습니다')
    expect(screen.getByLabelText(/^호스트/)).toHaveValue('dc1.corp.test')
  })
})

async function failure(stage: string): Promise<unknown> {
  const { ApiError } = await import('../api/problem')
  return new ApiError(422, {
    type: 'https://sales.neoine.test/problems/directory-verification-failed',
    title: 'Directory Verification Failed',
    status: 422,
    detail: '서버 문구',
    stage,
  })
}

describe('설정 화면: 저장된 비밀번호는 마스크로만 보인다 (AC4)', () => {
  it('shows the saved values and a fixed mask in the password field', async () => {
    await openSettings()

    expect(screen.getByLabelText(/^호스트/)).toHaveValue('dc1.corp.test')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(screen.getByLabelText(/^바인드 계정/)).toHaveValue('CORP\\svc-sales')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(password()).toHaveValue(BIND_PASSWORD_MASK)
    expect(password()).toHaveAttribute('type', 'password')
    expect(directory().getByText(KEEP_HINT, { exact: false })).toBeInTheDocument()
  })

  it('shows the discovered Base DN as read-only text, not as an input', async () => {
    await openSettings()

    expect(directory().getByText('dc=corp,dc=test')).toBeInTheDocument()
    expect(screen.queryByLabelText(/^Base DN/)).not.toBeInTheDocument()
    expect(screen.queryByDisplayValue('dc=corp,dc=test')).not.toBeInTheDocument()
  })

  it('has the seven inputs plus the admin password confirmation, and none of the removed ones', async () => {
    await openSettings()
    const form = screen.getByLabelText(/^호스트/).closest('form') as HTMLFormElement

    expect(form.querySelectorAll('input, select, textarea')).toHaveLength(8)
    expect(within(form).getByLabelText(/현재 관리자 비밀번호/)).toBeInTheDocument()
    for (const label of REMOVED_LABELS) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
  })

  it('sends null for the bind password while the mask is untouched', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue({ ...DIRECTORY_SAVED, revision: 4 })
    const { user } = await openSettings()
    setField(/연결 제한 시간/, '9')

    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ host: 'dc1.corp.test', connectTimeoutSeconds: 9, bindPassword: null }),
      { password: null, expectedRevision: 3 },
    )
  })

  it('clears the mask when the field is used and sends what is typed', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings()

    await user.click(password())
    await user.type(password(), 'Brand-new-pw-4!')
    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ bindPassword: 'Brand-new-pw-4!' }), expect.anything())
  })

  it('treats a typed mask text as the new password (no string comparison)', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings()

    await user.click(password())
    await user.type(password(), BIND_PASSWORD_MASK)
    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ bindPassword: BIND_PASSWORD_MASK }), expect.anything())
  })

  it('goes back to the mask after a successful save and never shows the typed password', async () => {
    vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings()
    await user.click(password())
    await user.type(password(), 'Brand-new-pw-4!')

    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    await waitFor(() => expect(password()).toHaveValue(BIND_PASSWORD_MASK))
    expect(screen.queryByDisplayValue('Brand-new-pw-4!')).not.toBeInTheDocument()
  })

  it('goes back to the mask after a failed test too', async () => {
    vi.spyOn(gateway.settings, 'testDirectory').mockRejectedValue(await failure('connect'))
    const { user } = await openSettings()
    await user.click(password())
    await user.type(password(), 'Typed-and-rejected-1!')

    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    await directory().findByRole('alert')
    expect(screen.queryByDisplayValue('Typed-and-rejected-1!')).not.toBeInTheDocument()
  })
})

describe('설정 화면: 서버나 계정을 바꾸면 비밀번호를 다시 입력한다 (AC4)', () => {
  async function changeAndSave(change: (user: Rendered['user']) => Promise<void> | void) {
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const view = await openSettings()
    await change(view.user)
    return { ...view, save }
  }

  it.each([
    ['host', () => setField(/^호스트/, 'dc9.corp.test')],
    ['port', () => setField(/^포트/, '3269')],
    ['bind account', () => setField(/^바인드 계정/, 'CORP\\other')],
    [
      'security',
      () => {
        fireEvent.change(screen.getByLabelText(/^보안 연결/), { target: { value: 'starttls' } })
      },
    ],
  ] as const)('clears the mask and asks to retype when the %s changes', async (_name, change) => {
    await changeAndSave(change)

    expect(password()).toHaveValue('')
    expect(directory().getByText(RETYPE_NOTICE, { exact: false })).toBeInTheDocument()
  })

  it('refuses to save without a new password after the change', async () => {
    const { user, save } = await changeAndSave(() => setField(/^호스트/, 'dc9.corp.test'))

    await user.click(directory().getByRole('button', { name: '저장' }))

    expect(await directory().findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(save).not.toHaveBeenCalled()
  })

  it('saves once the new password is typed', async () => {
    const { user, save } = await changeAndSave(() => setField(/^호스트/, 'dc9.corp.test'))
    vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    await user.type(password(), 'Typed-after-change-5!')

    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ host: 'dc9.corp.test', bindPassword: 'Typed-after-change-5!' }),
      expect.anything(),
    )
  })

  it('keeps the mask when only the user filter or the timeout changes', async () => {
    await changeAndSave(() => {
      setField(/사용자 검색 필터/, '(uid={login_id})')
      setField(/연결 제한 시간/, '11')
    })

    expect(password()).toHaveValue(BIND_PASSWORD_MASK)
    expect(screen.queryByText(RETYPE_NOTICE, { exact: false })).not.toBeInTheDocument()
  })

  it('drops the notice when the value is changed back to the saved one before typing', async () => {
    await changeAndSave(() => setField(/^호스트/, 'dc1.corp.test'))

    expect(password()).toHaveValue(BIND_PASSWORD_MASK)
    expect(screen.queryByText(RETYPE_NOTICE, { exact: false })).not.toBeInTheDocument()
  })
})

describe('설정 화면: 저장된 비밀번호를 읽을 수 없을 때 (AC10)', () => {
  const UNREADABLE: DirectorySettings = { ...DIRECTORY_SAVED, bindCredentialStatus: 'unreadable' }

  it('shows an empty password field and explains that it has to be typed again', async () => {
    await openSettings(UNREADABLE)

    expect(password()).toHaveValue('')
    expect(directory().getByText(UNREADABLE_NOTICE, { exact: false })).toBeInTheDocument()
  })

  it('refuses to save or test with nothing typed', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const { user } = await openSettings(UNREADABLE)

    await user.click(directory().getByRole('button', { name: '저장' }))

    expect(await directory().findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(save).not.toHaveBeenCalled()
    expect(test).not.toHaveBeenCalled()
  })

  it('saves normally once a new password is typed', async () => {
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings(UNREADABLE)
    await user.type(password(), 'Typed-again-6!')

    await user.click(directory().getByRole('button', { name: '저장' }))

    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ bindPassword: 'Typed-again-6!' }), expect.anything())
  })

  it('does not show the notice for a readable credential', async () => {
    await openSettings()

    expect(screen.queryByText(UNREADABLE_NOTICE, { exact: false })).not.toBeInTheDocument()
  })
})
