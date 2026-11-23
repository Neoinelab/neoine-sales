import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { DirectorySettings } from '../model/types'
import { DIRECTORY_SAVED } from '../../test/directoryFixtures'
import { fillDirectoryForm, passDirectoryTest, selectSecurity, setField } from '../../test/directoryForm'
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
  await screen.findByRole('heading', { name: '인증 방식' })
  await view.user.click(screen.getByRole('button', { name: 'AD 연동' }))
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
  // 최초 설정 화면에는 호스트·포트·보안 연결·바인드 계정·바인드 비밀번호·사용자 필터·연결 제한 시간 7개 입력 칸만 있다.
  it('has exactly the seven inputs: host, port, security, bind account, bind password, user filter, connect timeout', async () => {
    // when: 최초 설정의 AD 서버 등록 화면을 연다
    await openSetup()
    const form = screen.getByRole('heading', { name: 'AD 서버 등록' }).closest('form') as HTMLFormElement

    // then: 일곱 칸이 모두 있고 입력 요소가 정확히 7개다
    for (const label of [/^호스트/, /^포트/, /^보안 연결/, /^바인드 계정/, /^바인드 비밀번호/, /사용자 검색 필터/, /연결 제한 시간/]) {
      expect(within(form).getByLabelText(label)).toBeInTheDocument()
    }
    expect(form.querySelectorAll('input, select, textarea')).toHaveLength(7)
  })

  // 폐지된 입력 칸(서버 URL·Base DN·CA 인증서 등)은 보이지 않는다.
  it('has none of the removed inputs', async () => {
    // when: 최초 설정의 AD 서버 등록 화면을 연다
    await openSetup()

    // then: 폐지된 칸 라벨과 체크박스가 없다
    for (const label of REMOVED_LABELS) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })

  // 처음 열면 SSL·636 포트·기본 필터·5초 제한 시간이고 호스트·비밀번호는 비어 있다.
  it('opens with SSL on 636, the default filter, a 5 second timeout and an empty password', async () => {
    // when: 최초 설정의 AD 서버 등록 화면을 연다
    await openSetup()

    // then: 보안 연결 ssl, 포트 636, 기본 사용자 필터, 제한 시간 5이고 호스트·비밀번호가 비어 있다
    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue('(&(objectClass=user)(sAMAccountName={login_id}))')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.getByLabelText(/^호스트/)).toHaveValue('')
    expect(password()).toHaveValue('')
  })

  // 보안 연결 선택지는 없음·SSL·StartTLS 세 가지다.
  it('offers none, SSL and StartTLS for the security mode', async () => {
    // when: 최초 설정의 AD 서버 등록 화면을 연다
    await openSetup()

    // then: 선택지가 none·ssl·starttls 순서로 이름과 함께 나온다
    const options = within(screen.getByLabelText(/^보안 연결/)).getAllByRole('option')
    expect(options.map((o) => [(o as HTMLOptionElement).value, o.textContent])).toEqual([
      ['none', '없음'],
      ['ssl', 'SSL'],
      ['starttls', 'StartTLS'],
    ])
  })

  // 바인드 비밀번호는 가려지고 브라우저 자동 완성에서 제외된다.
  it('keeps the bind password out of autofill and masks it', async () => {
    // when: 최초 설정의 AD 서버 등록 화면을 연다
    await openSetup()

    // then: 비밀번호 칸은 password 타입·new-password 자동 완성이고 호스트 칸은 autocomplete off다
    expect(password()).toHaveAttribute('type', 'password')
    expect(password()).toHaveAttribute('autocomplete', 'new-password')
    expect(screen.getByLabelText(/^호스트/)).toHaveAttribute('autocomplete', 'off')
  })

  // 처음 등록할 때는 저장된 비밀번호 안내 문구가 없다.
  it('does not show the stored-password hint when registering for the first time', async () => {
    // when: 최초 설정의 AD 서버 등록 화면을 연다
    await openSetup()

    // then: "그대로 두면 저장된 비밀번호를 씁니다" 안내가 없다
    expect(screen.queryByText(KEEP_HINT, { exact: false })).not.toBeInTheDocument()
  })
})

describe('보안 연결 방식과 포트 (AC8)', () => {
  // 보안 연결을 바꾸면 그 방식의 기본 포트로 바뀐다.
  it('switches to the default port of the chosen mode', async () => {
    // given: 최초 설정의 AD 서버 등록 화면을 연다
    const { user } = await openSetup()

    // when: none, starttls, ssl 순서로 고른다
    await selectSecurity(user, 'none')

    // then: 포트가 389, 389, 636으로 바뀐다
    expect(screen.getByLabelText(/^포트/)).toHaveValue(389)
    await selectSecurity(user, 'starttls')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(389)
    await selectSecurity(user, 'ssl')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
  })

  // 포트 칸을 비운 채 방식을 바꾸면 기본 포트를 채운다.
  it('fills the default port when the port field was emptied', async () => {
    const { user } = await openSetup()

    // given: 포트 칸을 비운다
    setField(/^포트/, '')

    // when: 보안 연결을 none으로 고른다
    await selectSecurity(user, 'none')

    // then: 포트가 389다
    expect(screen.getByLabelText(/^포트/)).toHaveValue(389)
  })

  // 사용자가 입력한 포트는 방식을 바꿔도 유지한다.
  it('keeps a port the user typed when the mode changes', async () => {
    const { user } = await openSetup()

    // given: 포트에 3269를 입력한다
    setField(/^포트/, '3269')

    // when: 보안 연결을 starttls로 고른다
    await selectSecurity(user, 'starttls')

    // then: 포트가 3269 그대로다
    expect(screen.getByLabelText(/^포트/)).toHaveValue(3269)
  })

  // none 방식에서만 암호화되지 않는다는 경고를 보인다.
  it('warns that nothing is encrypted for the none mode only', async () => {
    const { user } = await openSetup()

    // when: 보안 연결을 none으로 고른다
    await selectSecurity(user, 'none')

    // then: 평문 경고만 보이고 인증서 미검증 경고는 없다
    expect(screen.getByText(PLAIN_WARNING, { exact: false })).toBeInTheDocument()
    expect(screen.queryByText(NO_VERIFY_WARNING, { exact: false })).not.toBeInTheDocument()
  })

  // ssl·starttls 방식에서는 서버 인증서를 검증하지 않는다는 경고를 보인다.
  it.each(['ssl', 'starttls'] as const)('warns that the server certificate is not verified for %s', async (mode) => {
    const { user } = await openSetup()

    // given: none을 먼저 고른다
    await selectSecurity(user, 'none')

    // when: 해당 방식(ssl 또는 starttls)을 고른다
    await selectSecurity(user, mode)

    // then: 인증서 미검증 경고만 보이고 평문 경고는 없다
    expect(screen.getByText(NO_VERIFY_WARNING, { exact: false })).toBeInTheDocument()
    expect(screen.queryByText(PLAIN_WARNING, { exact: false })).not.toBeInTheDocument()
  })
})

describe('최초 설정에서는 바인드 비밀번호가 필수다 (AC4)', () => {
  // 비밀번호가 비어 있으면 요청을 보내지 않고 입력을 요구한다.
  it('asks for the bind password before sending anything', async () => {
    const { user } = await openSetup()

    // given: 비밀번호만 비운 채 나머지를 채운다
    const save = vi.spyOn(gateway.setup, 'saveDirectory')
    const test = vi.spyOn(gateway.setup, 'testDirectory')
    fillDirectoryForm({ bindPassword: '' })

    // when: "연결 테스트"를 누른다
    await user.click(screen.getByRole('button', { name: '연결 테스트' }))

    // then: 비밀번호 입력 안내가 보이고 테스트·저장 요청은 보내지 않으며 등록 화면에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(test).not.toHaveBeenCalled()
    expect(save).not.toHaveBeenCalled()
    expect(screen.getByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
  })

  // 입력한 7개 값과 비밀번호를 그대로 저장 요청에 담는다.
  it('sends the seven values with the typed password', async () => {
    const { user } = await openSetup()

    // given: 호스트·계정·비밀번호를 채우고 보안 연결을 starttls로 고른다
    const save = vi.spyOn(gateway.setup, 'saveDirectory')
    fillDirectoryForm({ host: 'dc2.corp.test', bindAccount: 'svc@corp.test', bindPassword: 'Typed-pw-3!' })
    await selectSecurity(user, 'starttls')
    await passDirectoryTest(user)

    // when: "AD 서버 등록"을 누른다
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    // then: 저장 위치 단계로 넘어가고 저장 요청에 일곱 값이 담긴다
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

  // 등록이 실패하면 실패한 단계를 설명하고 다른 입력은 유지한다.
  it('explains the failed stage and keeps the other inputs after a failed registration', async () => {
    const { user } = await openSetup()

    // given: 서비스 계정 바인드 단계 실패를 돌려주도록 하고 폼을 채운다
    vi.spyOn(gateway.setup, 'saveDirectory').mockRejectedValue(await failure('service_bind'))
    fillDirectoryForm()
    await passDirectoryTest(user)

    // when: "AD 서버 등록"을 누른다
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    // then: 바인드 실패 안내가 보이고 호스트 값이 그대로다
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
  // 저장된 설정의 값과 고정 마스크를 비밀번호 칸에 보이고 유지 안내를 보인다.
  // 테스트 코드: IN-059
  it('shows the saved values and a fixed mask in the password field', async () => {
    // when: 외부연동 화면을 연다 (전제: 예시 AD 설정이 저장되어 있다)
    await openSettings()

    // then: 7칸에 저장 값이 보이고 비밀번호 칸은 마스크이며 '그대로 두면 저장된 비밀번호를 씁니다' 안내가 있다
    expect(screen.getByLabelText(/^호스트/)).toHaveValue('dc1.corp.test')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(screen.getByLabelText(/^바인드 계정/)).toHaveValue('CORP\\svc-sales')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(password()).toHaveValue(BIND_PASSWORD_MASK)
    expect(password()).toHaveAttribute('type', 'password')
    expect(directory().getByText(KEEP_HINT, { exact: false })).toBeInTheDocument()
  })

  // 찾은 Base DN은 입력 칸이 아니라 읽기 전용 텍스트로 보인다.
  // 테스트 코드: IN-059
  it('shows the discovered Base DN as read-only text, not as an input', async () => {
    // when: 외부연동 화면을 연다 (전제: 예시 AD 설정이 저장되어 있다)
    await openSettings()

    // then: Base DN은 텍스트로만 있고 입력 칸·값으로는 없다
    expect(directory().getByText('dc=corp,dc=test')).toBeInTheDocument()
    expect(screen.queryByLabelText(/^Base DN/)).not.toBeInTheDocument()
    expect(screen.queryByDisplayValue('dc=corp,dc=test')).not.toBeInTheDocument()
  })

  // 설정 화면은 입력 칸 7개와 현재 관리자 비밀번호 칸뿐이고 폐지된 칸이 없다.
  // 테스트 코드: IN-069
  it('has the seven inputs plus the admin password confirmation, and none of the removed ones', async () => {
    // given: 예시 AD 설정이 저장되어 있다
    await openSettings()

    // when: 외부연동 화면의 폼을 본다
    const form = screen.getByLabelText(/^호스트/).closest('form') as HTMLFormElement

    // then: 입력 8개(7칸+admin 비밀번호)이고 폐지된 칸이 없다
    expect(form.querySelectorAll('input, select, textarea')).toHaveLength(8)
    expect(within(form).getByLabelText(/현재 관리자 비밀번호/)).toBeInTheDocument()
    for (const label of REMOVED_LABELS) expect(screen.queryByLabelText(label)).not.toBeInTheDocument()
  })

  // 손대지 않은 마스크는 바인드 비밀번호를 보내지 않는다(null).
  // 테스트 코드: IN-072, IN-074
  it('sends null for the bind password while the mask is untouched', async () => {
    // given: 예시 AD 설정이 보이고 연결 제한 시간만 바꿨다
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue({ ...DIRECTORY_SAVED, revision: 4 })
    const { user } = await openSettings()
    setField(/연결 제한 시간/, '9')

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 바인드 비밀번호 null로 요청하고 저장했습니다가 보인다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ host: 'dc1.corp.test', connectTimeoutSeconds: 9, bindPassword: null }),
      { password: null, expectedRevision: 3 },
    )
  })

  // 칸을 쓰면 마스크가 비워지고 입력한 값을 보낸다.
  // 테스트 코드: IN-072
  it('clears the mask when the field is used and sends what is typed', async () => {
    // given: 예시 AD 설정이 보인다
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings()

    // when: 비밀번호 칸을 눌러 새 비밀번호를 입력하고 저장한다
    await user.click(password())
    await user.type(password(), 'Brand-new-pw-4!')
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 입력한 값을 바인드 비밀번호로 보낸다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ bindPassword: 'Brand-new-pw-4!' }), expect.anything())
  })

  // 마스크와 같은 글자를 직접 입력해도 새 비밀번호로 보낸다.
  // 테스트 코드: IN-072
  it('treats a typed mask text as the new password (no string comparison)', async () => {
    // given: 예시 AD 설정이 보인다
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings()

    // when: 비밀번호 칸에 ********를 직접 입력하고 저장한다
    await user.click(password())
    await user.type(password(), BIND_PASSWORD_MASK)
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: bind_password로 ********를 보낸다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ bindPassword: BIND_PASSWORD_MASK }), expect.anything())
  })

  // 저장에 성공하면 마스크로 돌아가고 입력한 비밀번호는 화면에 남지 않는다.
  // 테스트 코드: IN-064
  it('goes back to the mask after a successful save and never shows the typed password', async () => {
    // given: 새 바인드 비밀번호를 입력했다
    vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings()
    await user.click(password())
    await user.type(password(), 'Brand-new-pw-4!')

    // when: 저장한다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 저장했습니다 뒤 칸이 마스크로 돌아가고 입력한 값이 보이지 않는다
    await directory().findByText('저장했습니다')
    await waitFor(() => expect(password()).toHaveValue(BIND_PASSWORD_MASK))
    expect(screen.queryByDisplayValue('Brand-new-pw-4!')).not.toBeInTheDocument()
  })

  // 연결 테스트가 실패해도 마스크로 돌아가고 입력한 비밀번호는 화면에 남지 않는다.
  // 테스트 코드: IN-064
  it('goes back to the mask after a failed test too', async () => {
    // given: 새 바인드 비밀번호를 입력했다
    vi.spyOn(gateway.settings, 'testDirectory').mockRejectedValue(await failure('connect'))
    const { user } = await openSettings()
    await user.click(password())
    await user.type(password(), 'Typed-and-rejected-1!')

    await user.click(directory().getByRole('button', { name: '연결 테스트' }))

    // when: 연결 테스트가 실패한다
    await directory().findByRole('alert')

    // then: 오류 알림이 보이고 입력한 값이 화면에 남지 않는다
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

  // 엔드포인트·계정 칸을 바꾸면 마스크를 비우고 다시 입력하라고 안내한다.
  // 테스트 코드: IN-073
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
    // when: 호스트·포트·바인드 계정·보안 연결 중 하나를 바꾼다 (전제: 예시 AD 설정이 보인다)
    await changeAndSave(change)

    // then: 비밀번호 칸이 비고 '서버나 바인드 계정을 바꿨으므로 비밀번호를 다시 입력하세요' 안내가 보인다
    expect(password()).toHaveValue('')
    expect(directory().getByText(RETYPE_NOTICE, { exact: false })).toBeInTheDocument()
  })

  // 바꾼 뒤 새 비밀번호 없이 저장하면 요청 없이 입력을 요구한다.
  // 테스트 코드: IN-073
  it('refuses to save without a new password after the change', async () => {
    // given: 호스트를 바꿔 비밀번호 칸이 비었다
    const { user, save } = await changeAndSave(() => setField(/^호스트/, 'dc9.corp.test'))

    // when: 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: '바인드 비밀번호를 입력하세요'가 보이고 저장 요청은 없었다
    expect(await directory().findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(save).not.toHaveBeenCalled()
  })

  // 새 비밀번호를 입력하면 바꾼 접속 정보로 저장 요청이 간다.
  // 테스트 코드: IN-073
  it('saves once the new password is typed', async () => {
    // given: 호스트를 바꿨다
    const { user, save } = await changeAndSave(() => setField(/^호스트/, 'dc9.corp.test'))
    vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)

    // when: 새 비밀번호를 입력하고 저장한다
    await user.type(password(), 'Typed-after-change-5!')
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 새 호스트와 입력한 비밀번호로 저장한다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ host: 'dc9.corp.test', bindPassword: 'Typed-after-change-5!' }),
      expect.anything(),
    )
  })

  // 사용자 필터·연결 제한 시간만 바꾸면 마스크가 유지된다.
  // 테스트 코드: IN-074
  it('keeps the mask when only the user filter or the timeout changes', async () => {
    // when: 사용자 필터와 연결 제한 시간만 바꾼다 (전제: 예시 AD 설정이 보인다)
    await changeAndSave(() => {
      setField(/사용자 검색 필터/, '(uid={login_id})')
      setField(/연결 제한 시간/, '11')
    })

    // then: 비밀번호 칸은 마스크이고 재입력 안내는 없다
    expect(password()).toHaveValue(BIND_PASSWORD_MASK)
    expect(screen.queryByText(RETYPE_NOTICE, { exact: false })).not.toBeInTheDocument()
  })

  // 입력 전에 저장된 값으로 되돌리면 안내가 사라지고 마스크로 돌아간다.
  // 테스트 코드: IN-073
  it('drops the notice when the value is changed back to the saved one before typing', async () => {
    // when: 저장된 호스트로 되돌린다 (전제: 호스트를 바꿨다 되돌린다)
    await changeAndSave(() => setField(/^호스트/, 'dc1.corp.test'))

    // then: 마스크로 돌아가고 재입력 안내가 없다
    expect(password()).toHaveValue(BIND_PASSWORD_MASK)
    expect(screen.queryByText(RETYPE_NOTICE, { exact: false })).not.toBeInTheDocument()
  })
})

describe('설정 화면: 저장된 비밀번호를 읽을 수 없을 때 (AC10)', () => {
  const UNREADABLE: DirectorySettings = { ...DIRECTORY_SAVED, bindCredentialStatus: 'unreadable' }

  // 저장된 비밀번호를 읽을 수 없으면 빈 칸과 다시 입력하라는 안내를 보인다.
  // 테스트 코드: IN-075
  it('shows an empty password field and explains that it has to be typed again', async () => {
    // when: 외부연동 화면을 연다 (전제: 저장된 비밀번호를 읽을 수 없다)
    await openSettings(UNREADABLE)

    // then: 비밀번호 칸이 비고 '저장된 바인드 비밀번호를 읽을 수 없습니다. 다시 입력하세요' 안내가 보인다
    expect(password()).toHaveValue('')
    expect(directory().getByText(UNREADABLE_NOTICE, { exact: false })).toBeInTheDocument()
  })

  // 읽을 수 없는 비밀번호는 입력 없이 저장하면 요청 없이 입력을 요구한다.
  // 테스트 코드: IN-075
  it('refuses to save or test with nothing typed', async () => {
    // given: 저장된 비밀번호를 읽을 수 없다
    const save = vi.spyOn(gateway.settings, 'saveDirectory')
    const test = vi.spyOn(gateway.settings, 'testDirectory')
    const { user } = await openSettings(UNREADABLE)

    // when: 비밀번호 없이 저장을 누른다
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: '바인드 비밀번호를 입력하세요'가 보이고 저장·테스트 요청은 없었다
    expect(await directory().findByRole('alert')).toHaveTextContent('바인드 비밀번호를 입력하세요')
    expect(save).not.toHaveBeenCalled()
    expect(test).not.toHaveBeenCalled()
  })

  // 읽을 수 없는 경우에도 새 비밀번호를 입력하면 정상 저장된다.
  // 테스트 코드: IN-075
  it('saves normally once a new password is typed', async () => {
    // given: 저장된 비밀번호를 읽을 수 없다
    const save = vi.spyOn(gateway.settings, 'saveDirectory').mockResolvedValue(DIRECTORY_SAVED)
    const { user } = await openSettings(UNREADABLE)

    // when: 새 비밀번호를 입력하고 저장한다
    await user.type(password(), 'Typed-again-6!')
    await user.click(directory().getByRole('button', { name: '저장' }))

    // then: 입력한 비밀번호로 저장한다
    await directory().findByText('저장했습니다')
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ bindPassword: 'Typed-again-6!' }), expect.anything())
  })

  // 읽을 수 있는 비밀번호에는 읽을 수 없다는 안내가 없다.
  // 테스트 코드: IN-075
  it('does not show the notice for a readable credential', async () => {
    // when: 외부연동 화면을 연다 (전제: 저장된 비밀번호를 읽을 수 있다)
    await openSettings()

    // then: 안내가 없다
    expect(screen.queryByText(UNREADABLE_NOTICE, { exact: false })).not.toBeInTheDocument()
  })
})
