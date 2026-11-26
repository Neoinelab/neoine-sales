import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError, type Problem } from '../../shared/api/problem'
import { defaultDealsUrlPattern } from '../../test/dealsUrl'
import { fillDirectoryForm, passDirectoryTest } from '../../test/directoryForm'
import { openFreshSetup, openLocalAdminStep, openLocalStorageStep, openUserMenu, renderLocalAt } from '../../test/localAccounts'
import { renderAt } from '../../test/mockApp'
import { mockControl } from '../../test/fake/default'

afterEach(() => vi.restoreAllMocks())

type Rendered = Awaited<ReturnType<typeof renderAt>>

const steps = () => within(screen.getByRole('list', { name: '설정 단계' }))
const stepItem = (label: string) => steps().getByText(label).closest('li') as HTMLElement

function problemOf(status: number, kind: string, detail: string): ApiError {
  return new ApiError(status, { type: `https://sales.neoine.test/problems/${kind}`, title: kind, status, detail })
}


/** 설정이 필요한 상태(방식 미선택)로 주소를 연다. */
async function openUnconfigured(url: string, options: { role: null } = { role: null }): Promise<Rendered> {
  const reset = mockControl.resetData.bind(mockControl)
  vi.spyOn(mockControl, 'resetData').mockImplementation(() => {
    reset()
    mockControl.restartSetup()
  })
  return renderAt(url, options)
}

/** AD 방식으로 1·2단계를 마치고 관리자 등록 단계를 연다. */
async function openAdAdminStep(): Promise<Rendered> {
  const view = await openFreshSetup()
  await view.user.click(screen.getByRole('button', { name: 'AD 연동' }))
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  fillDirectoryForm()
  await passDirectoryTest(view.user)
  await view.user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
  await screen.findByRole('heading', { name: '파일 저장 위치' })
  await view.user.type(screen.getByLabelText('저장 경로'), '/data/neoine-sales/files')
  await view.user.click(screen.getByRole('button', { name: '저장 위치 등록' }))
  await screen.findByRole('heading', { name: '관리자 등록' })
  return view
}

/** AD 서버 등록 폼까지 연다. */
async function openAdForm(): Promise<Rendered> {
  const view = await openFreshSetup()
  await view.user.click(screen.getByRole('button', { name: 'AD 연동' }))
  await screen.findByRole('heading', { name: 'AD 서버 등록' })
  return view
}

describe('최초 설정 진입 (SU-046, SU-047)', () => {
  // 최초 설정이 필요하면 로그인 화면과 보호 화면 방문은 /setup으로 간다.
  // 테스트 코드: SU-046
  it.each(['/login', '/deals', '/admin/users'])('sends an anonymous visitor of %s to /setup while the setup is needed', async (path) => {
    // when: 해당 주소를 연다 (전제: 최초 설정이 끝나지 않았고 로그인하지 않았다)
    const { location } = await openUnconfigured(path)

    // then: 주소가 /setup이 된다
    await waitFor(() => expect(location()).toBe('/setup'))
  })

  // 설정이 끝난 시스템의 /setup은 로그인 화면으로 가고 AD 폼이 보이지 않는다.
  // 테스트 코드: SU-047
  it('sends an anonymous visitor of a finished AD system from /setup to the login page', async () => {
    // when: /setup을 연다 (전제: 최초 설정이 끝났고 로그인하지 않았다)
    const { location } = await renderAt('/setup', { role: null })

    // then: /login으로 가고 AD 폼은 보이지 않는다
    await waitFor(() => expect(location()).toBe('/login'))
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
  })

  // 테스트 코드: SU-047
  it('sends an anonymous visitor of a finished local system from /setup to the login page', async () => {
    // when: /setup을 연다 (전제: local로 설정이 끝났다)
    const { location } = await renderLocalAt('/setup', { role: null })

    // then: /login으로 가고 AD 폼은 보이지 않는다
    await waitFor(() => expect(location()).toBe('/login'))
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
  })

  // 테스트 코드: SU-047
  it('does not keep a signed-in admin on /setup', async () => {
    // when: /setup을 연다 (전제: admin으로 로그인했다)
    const { location } = await renderAt('/setup', { role: 'admin' })

    // then: /setup에 머물지 않는다
    await waitFor(() => expect(location()).not.toBe('/setup'))
  })

  // 테스트 코드: SU-047
  it('shows the server message as an alert when the status cannot be read', async () => {
    // given: 진행 상태 조회가 401 "로그인이 필요합니다."로 실패한다
    vi.spyOn(gateway.setup, 'status').mockRejectedValue(problemOf(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when: /setup을 연다
    await renderAt('/setup', { role: null })

    // then: 오류가 role=alert로 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  })
})

describe('인증 방식 단계 (SU-048~SU-051, SU-059)', () => {
  // 새 시스템의 /setup은 인증 방식 선택과 세 단계 표시로 시작한다.
  // 테스트 코드: SU-048
  it('starts with the auth mode choice and the three step labels', async () => {
    // when: /setup을 연다 (전제: 최초 설정이 처음 상태다)
    await openFreshSetup()

    // then: 제목, 두 버튼, 세 단계 이름, 1단계 현재 표시가 보이고 다음 단계 칸은 없다
    expect(screen.getByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'AD 연동' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '앱에서 직접 관리' })).toBeEnabled()
    expect(steps().getAllByRole('listitem').map((li) => li.textContent)).toEqual(['1. 인증 방식', '2. 파일 저장 위치', '3. 관리자 등록'])
    expect(stepItem('1. 인증 방식')).toHaveAttribute('aria-current', 'step')
    expect(screen.queryByLabelText('저장 경로')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('AD 아이디')).not.toBeInTheDocument()
  })

  // "앱에서 직접 관리"를 누르면 서버에 기록하고 AD 폼 없이 저장 위치 단계로 간다.
  // 테스트 코드: SU-049
  it('records local on the server and moves to the storage step without an AD form', async () => {
    // given: 인증 방식 선택 화면이다
    const { user } = await openFreshSetup()
    const choose = vi.spyOn(gateway.setup, 'chooseAuthMode')

    // when: "앱에서 직접 관리"를 누른다
    await user.click(screen.getByRole('button', { name: '앱에서 직접 관리' }))

    // then: local로 1회 요청하고 "파일 저장 위치"가 보이며 AD 폼은 없고 1단계는 완료다
    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect(choose).toHaveBeenCalledTimes(1) // 요청 횟수가 사용자에게 보이는 결과(한 번만 기록)다
    expect(choose).toHaveBeenCalledWith('local')
    expect(screen.queryByRole('heading', { name: 'AD 서버 등록' })).not.toBeInTheDocument()
    expect(stepItem('1. 인증 방식')).toHaveTextContent('완료')
  })

  // 방식 선택이 거절되면 서버 문구를 보이고 선택 화면에 머문다.
  // 테스트 코드: SU-050
  it.each([
    ['closed', problemOf(409, 'invalid-state', '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다')],
    ['other', problemOf(500, 'internal', '서버 오류가 발생했습니다.')],
  ])('shows the server message and stays on the choice when choosing fails (%s)', async (_name, failure) => {
    // given: 방식 선택 요청이 실패한다
    const { user } = await openFreshSetup()
    vi.spyOn(gateway.setup, 'chooseAuthMode').mockRejectedValue(failure)

    // when: "앱에서 직접 관리"를 누른다
    await user.click(screen.getByRole('button', { name: '앱에서 직접 관리' }))

    // then: 그 문구가 role=alert로 보이고 "인증 방식" 제목에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent(failure.message)
    expect(screen.getByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
  })

  // "AD 연동"은 서버를 부르지 않고 기본값이 채워진 AD 폼을 열고 되돌아갈 수 있다.
  // 테스트 코드: SU-051
  it('opens the AD form with defaults without calling the server and can go back', async () => {
    // given: 인증 방식 선택 화면이다
    const { user } = await openFreshSetup()
    const choose = vi.spyOn(gateway.setup, 'chooseAuthMode')

    // when: "AD 연동"을 누른다
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))

    // then: 방식 선택 요청 없이 "AD 서버 등록"이 열리고 기본값이 채워지며 없어진 칸은 없다
    expect(await screen.findByRole('heading', { name: 'AD 서버 등록' })).toBeInTheDocument()
    expect(choose).not.toHaveBeenCalled()
    expect(screen.getByLabelText(/^보안 연결/)).toHaveValue('ssl')
    expect(screen.getByLabelText(/^포트/)).toHaveValue(636)
    expect(screen.getByLabelText(/사용자 검색 필터/)).toHaveValue('(&(objectClass=user)(sAMAccountName={login_id}))')
    expect(screen.getByLabelText(/연결 제한 시간/)).toHaveValue(5)
    expect(screen.queryByLabelText(/^바인드 비밀번호/)).not.toBeInTheDocument()
    for (const removed of [/서버 URL/, /StartTLS 사용/, /CA 인증서/, /바인드 템플릿/, /^Base DN/, /속성/, /응답 제한 시간/]) {
      expect(screen.queryByLabelText(removed)).not.toBeInTheDocument()
    }

    // when: "인증 방식 다시 선택"을 누른다
    await user.click(screen.getByRole('button', { name: '인증 방식 다시 선택' }))

    // then: "인증 방식" 제목이 보인다
    expect(await screen.findByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
  })

  // "인증 방식 다시 선택"으로 선택 화면에 돌아가 AD로 바꿀 수 있다.
  // 테스트 코드: SU-059
  it('goes back from the storage step and switches to AD', async () => {
    // given: local을 골라 저장 위치 단계에 있다
    const { user } = await openLocalStorageStep()

    // when: "인증 방식 다시 선택" → "AD 연동" → 호스트 dc2.corp.test로 AD 서버를 저장한다
    await user.click(screen.getByRole('button', { name: '인증 방식 다시 선택' }))
    expect(await screen.findByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm({ host: 'dc2.corp.test' })
    await passDirectoryTest(user)
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    // then: "파일 저장 위치"로 간다(저장 위치가 아직 없으므로)
    expect(await screen.findByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
  })

  // 테스트 코드: SU-059
  it('goes back from the local admin step and switches to AD, ending at the admin step', async () => {
    // given: local 관리자 등록 단계에 있다(저장 위치는 이미 있다)
    const { user } = await openLocalAdminStep()

    // when: "인증 방식 다시 선택" → "AD 연동" → AD 서버를 저장한다
    await user.click(screen.getByRole('button', { name: '인증 방식 다시 선택' }))
    expect(await screen.findByRole('heading', { name: '인증 방식' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm({ host: 'dc2.corp.test' })
    await passDirectoryTest(user)
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))

    // then: 저장 위치를 다시 묻지 않고 "관리자 등록"으로 간다
    expect(await screen.findByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })
})

describe('파일 저장 위치 단계 (SU-056~SU-058)', () => {
  // 저장 위치 단계는 안내를 보이고 잘못된 경로는 서버 문구로 거절하며 입력을 유지한다.
  // 테스트 코드: SU-056
  it('explains the location and starts with an empty path', async () => {
    // when: 화면을 본다 (전제: 저장 위치 단계다)
    await openLocalStorageStep()

    // then: 안내 문구가 보이고 "저장 경로"는 처음 빈 값이다
    expect(screen.getByText(/예: \/var\/lib\/neoine-sales\/files/)).toBeInTheDocument()
    expect(screen.getByText(/위치를 바꿔도 기존 파일 이동은 관리자가 수작업으로 처리합니다/)).toBeInTheDocument()
    expect(screen.getByLabelText('저장 경로')).toHaveValue('')
  })

  // 테스트 코드: SU-056
  it.each([
    ['data/files', '절대 경로를 입력하세요.'],
    ['', '절대 경로를 입력하세요.'],
    ['/x/../y', '절대 경로를 입력하세요.'],
    ['/readonly/files', '해당 위치에 쓸 수 없습니다.'],
  ])('rejects the path %j with the server message and keeps the input', async (path, message) => {
    // given: 저장 위치 단계다
    const { user } = await openLocalStorageStep()
    if (path) await user.type(screen.getByLabelText('저장 경로'), path)

    // when: "저장 위치 등록"을 누른다
    await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))

    // then: 서버 문구가 role=alert로 보이고 입력값이 그대로이며 제목에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByLabelText('저장 경로')).toHaveValue(path)
    expect(screen.getByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
  })

  // 쓰기 테스트는 성공 알림만 보이고 저장하지 않으며 다시 하면 이전 결과를 지운다.
  // 테스트 코드: SU-057
  it('shows only a success notice for the write test and does not save', async () => {
    // given: 저장 위치 단계에 경로를 넣었다
    const { user } = await openLocalStorageStep()
    await user.type(screen.getByLabelText('저장 경로'), '/data/neoine-sales/files')

    // when: "쓰기 테스트"를 누른다
    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    // then: 성공 알림이 보이고 단계에 머물며 저장되지 않았다
    expect(await screen.findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
    expect(screen.getByRole('heading', { name: '파일 저장 위치' })).toBeInTheDocument()
    expect((await gateway.setup.status()).storageDone).toBe(false)
  })

  // 테스트 코드: SU-057
  it('shows the server message for an unwritable location and clears it on the next run', async () => {
    // given: 쓸 수 없는 경로를 넣고 쓰기 테스트에 실패했다
    const { user } = await openLocalStorageStep()
    await user.type(screen.getByLabelText('저장 경로'), '/readonly/files')
    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('해당 위치에 쓸 수 없습니다.')
    expect(screen.getByLabelText('저장 경로')).toHaveValue('/readonly/files')

    // when: 경로를 고쳐 다시 "쓰기 테스트"를 누른다
    await user.clear(screen.getByLabelText('저장 경로'))
    await user.type(screen.getByLabelText('저장 경로'), '/data/ok')
    await user.click(screen.getByRole('button', { name: '쓰기 테스트' }))

    // then: 이전 오류가 사라지고 새 결과(성공 알림)가 보인다
    expect(await screen.findByRole('status')).toHaveTextContent('쓰기 테스트에 성공했습니다.')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // 저장 위치를 등록해야 관리자 등록 단계가 열린다.
  // 테스트 코드: SU-058
  it('opens the admin step only after the location is registered', async () => {
    // given: AD 서버를 저장해 저장 위치 단계에 있다
    const { user } = await openAdForm()
    fillDirectoryForm()
    await passDirectoryTest(user)
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByRole('heading', { name: '파일 저장 위치' })

    // when: 화면을 보고, 이어서 /data/neoine-sales/files로 "저장 위치 등록"을 누른다
    expect(screen.queryByLabelText('AD 아이디')).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('저장 경로'), '/data/neoine-sales/files')
    await user.click(screen.getByRole('button', { name: '저장 위치 등록' }))

    // then: "관리자 등록"이 보이고 2단계는 완료다
    expect(await screen.findByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
    expect(stepItem('2. 파일 저장 위치')).toHaveTextContent('완료')
  })
})

describe('관리자 등록 단계 (SU-060~SU-064)', () => {
  // AD 방식 관리자 등록이 성공하면 그 admin으로 로그인되어 Deals로 간다.
  // 테스트 코드: SU-060
  it('signs in as the new AD admin and moves to the deals list', async () => {
    // given: AD 방식으로 1·2단계를 마쳐 관리자 등록 단계다
    const { user, location } = await openAdAdminStep()

    // when: 화면을 보고, "AD 아이디" boss, "비밀번호" secret으로 "관리자 등록"을 누른다
    expect(screen.getByText('처음 등록하는 AD 계정이 관리자가 됩니다.')).toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('type', 'password')
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'current-password')
    await user.type(screen.getByLabelText('AD 아이디'), 'boss')
    await user.type(screen.getByLabelText('비밀번호'), 'secret')
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: Deals 기본 목록으로 가고 메뉴 "Admin"과 사용자 메뉴 "boss (admin)"이 보인다
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('admin')))
    expect(await screen.findByRole('link', { name: 'Admin' })).toBeInTheDocument()
    await openUserMenu(user)
    expect(screen.getByText('boss (admin)')).toBeInTheDocument()
  })

  // 관리자 등록이 거절되면 서버 문구를 보이고 비밀번호를 지운다.
  // 테스트 코드: SU-061
  it('shows the login failure message and clears the password', async () => {
    // given: AD 방식 관리자 등록 단계이고 등록 요청이 401로 실패한다
    const { user } = await openAdAdminStep()
    vi.spyOn(gateway.setup, 'registerAdmin').mockRejectedValue(problemOf(401, 'unauthenticated', '아이디 또는 비밀번호가 올바르지 않습니다'))

    // when: boss·secret으로 "관리자 등록"을 누른다
    await user.type(screen.getByLabelText('AD 아이디'), 'boss')
    await user.type(screen.getByLabelText('비밀번호'), 'secret')
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: 문구가 보이고 비밀번호는 비며 아이디는 그대로이고 제목에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent('아이디 또는 비밀번호가 올바르지 않습니다')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('boss')
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  // 테스트 코드: SU-061
  it('refuses an id that already belongs to an active user instead of promoting it', async () => {
    // given: AD 방식 관리자 등록 단계이고 같은 아이디(kim)의 재직 사용자가 있다
    const { user } = await openAdAdminStep()

    // when: kim·secret으로 "관리자 등록"을 누른다
    await user.type(screen.getByLabelText('AD 아이디'), 'kim')
    await user.type(screen.getByLabelText('비밀번호'), 'secret')
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: 중복 문구가 보이고 비밀번호는 비며 제목에 머문다(admin으로 올라가지 않는다)
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 존재하는 사용자입니다: kim')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  // local 방식 관리자 등록은 프로필 칸을 받고 성공하면 그 admin으로 로그인된다.
  // 테스트 코드: SU-062
  it('registers the local admin with the profile and signs in', async () => {
    // given: local 방식으로 저장 위치까지 마쳐 관리자 등록 단계다
    const { user, location } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')
    const saveDirectory = vi.spyOn(gateway.setup, 'saveDirectory')
    for (const label of ['아이디', '비밀번호', '비밀번호 확인', '이름', '이메일', '전화번호']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    }
    expect(screen.queryByLabelText('AD 아이디')).not.toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toHaveAttribute('autocomplete', 'new-password')

    // when: 모든 칸을 채워 등록한다
    await user.type(screen.getByLabelText('아이디'), 'boss')
    await user.type(screen.getByLabelText('비밀번호'), 'Passw0rd-ok')
    await user.type(screen.getByLabelText('비밀번호 확인'), 'Passw0rd-ok')
    await user.type(screen.getByLabelText('이름'), '보스')
    await user.type(screen.getByLabelText('이메일'), 'boss@corp.test')
    await user.type(screen.getByLabelText('전화번호'), '02-123-4567')
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: Deals 기본 목록으로 가고 사용자 메뉴에 "보스 (admin)"이 보이며 AD 서버 저장은 없었다
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('admin')))
    expect(register).toHaveBeenCalledWith('boss', 'Passw0rd-ok', { name: '보스', email: 'boss@corp.test', phone: '02-123-4567' })
    expect(saveDirectory).not.toHaveBeenCalled() // AD 서버 저장 요청이 없었다는 것이 케이스의 결과다
    await openUserMenu(user)
    expect(await screen.findByText('보스 (admin)')).toBeInTheDocument()
  })

  // 테스트 코드: SU-062
  it('sends an empty email and phone as null', async () => {
    // given: local 관리자 등록 단계다
    const { user, location } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')

    // when: 이메일·전화를 비워 둔 채 등록한다
    await user.type(screen.getByLabelText('아이디'), 'boss')
    await user.type(screen.getByLabelText('비밀번호'), 'Passw0rd-ok')
    await user.type(screen.getByLabelText('비밀번호 확인'), 'Passw0rd-ok')
    await user.type(screen.getByLabelText('이름'), '보스')
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: 요청의 이메일·전화는 null이고 Deals로 간다
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('admin')))
    expect(register).toHaveBeenCalledWith('boss', 'Passw0rd-ok', { name: '보스', email: null, phone: null })
  })

  // local 방식에서 비밀번호가 비거나 확인과 다르면 서버를 부르지 않는다.
  // 테스트 코드: SU-063
  it.each([
    ['both empty', '', '', '비밀번호를 입력하세요.'],
    ['password empty only', '', 'Passw0rd-ok', '비밀번호 확인이 일치하지 않습니다.'],
    ['confirmation differs', 'Passw0rd-ok', 'Passw0rd-no', '비밀번호 확인이 일치하지 않습니다.'],
  ])('does not call the server when %s', async (_name, password, confirm, message) => {
    // given: local 관리자 등록 단계에 아이디·이름을 넣었다
    const { user } = await openLocalAdminStep()
    const register = vi.spyOn(gateway.setup, 'registerAdmin')
    await user.type(screen.getByLabelText('아이디'), 'boss')
    await user.type(screen.getByLabelText('이름'), '보스')
    if (password) await user.type(screen.getByLabelText('비밀번호'), password)
    if (confirm) await user.type(screen.getByLabelText('비밀번호 확인'), confirm)

    // when: "관리자 등록"을 누른다
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: 해당 안내가 role=alert로 보이고 등록 요청은 없으며 단계에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(register).not.toHaveBeenCalled() // 서버에 가지 않았다는 것이 이 케이스의 결과다
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  // local 방식 서버 거절은 문구를 보이고 두 비밀번호 칸을 비우며 다른 입력은 유지한다.
  // 테스트 코드: SU-064
  it('shows the weak password message, clears both password fields, keeps the rest and flags the field', async () => {
    // given: local 관리자 등록 단계이고 서버가 errors[password]와 함께 비밀번호를 약하다고 거절한다
    const { user } = await openLocalAdminStep()
    const message = '비밀번호는 8자 이상이어야 합니다'
    vi.spyOn(gateway.setup, 'registerAdmin').mockRejectedValue(
      new ApiError(422, {
        type: 'https://sales.neoine.test/problems/invalid-value',
        title: 'Invalid Value',
        status: 422,
        detail: message,
        errors: [{ location: ['password'], message }],
      } as unknown as Problem),
    )
    await user.type(screen.getByLabelText('아이디'), 'boss')
    await user.type(screen.getByLabelText('비밀번호'), 'short7!')
    await user.type(screen.getByLabelText('비밀번호 확인'), 'short7!')
    await user.type(screen.getByLabelText('이름'), '보스')

    // when: "관리자 등록"을 누른다
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: 문구가 보이고 두 비밀번호 칸은 비며 아이디·이름은 그대로, 비밀번호 칸이 잘못된 칸으로 표시된다
    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('비밀번호 확인')).toHaveValue('')
    expect(screen.getByLabelText('아이디')).toHaveValue('boss')
    expect(screen.getByLabelText('이름')).toHaveValue('보스')
    expect(screen.getByLabelText('비밀번호')).toBeInvalid()
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })

  // 테스트 코드: SU-064
  it('shows the name message from the server and keeps the other inputs', async () => {
    // given: local 관리자 등록 단계이고 이름을 비워 서버가 거절한다
    const { user } = await openLocalAdminStep()
    await user.type(screen.getByLabelText('아이디'), 'boss')
    await user.type(screen.getByLabelText('비밀번호'), 'Passw0rd-ok')
    await user.type(screen.getByLabelText('비밀번호 확인'), 'Passw0rd-ok')

    // when: "관리자 등록"을 누른다
    await user.click(screen.getByRole('button', { name: '관리자 등록' }))

    // then: 이름 문구가 보이고 두 비밀번호 칸은 비며 아이디는 그대로이고 단계에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent('이름은(는) 비어 있을 수 없습니다')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('비밀번호 확인')).toHaveValue('')
    expect(screen.getByLabelText('아이디')).toHaveValue('boss')
    expect(screen.getByRole('heading', { name: '관리자 등록' })).toBeInTheDocument()
  })
})

describe('AD 연결 테스트와 등록', () => {
  // 테스트 코드: SU-055
  it.each([
    [false, false, 'AD 서버 등록'],
    [true, false, '파일 저장 위치'],
    [true, true, '관리자 등록'],
  ] as const)('opens the server-selected setup step (%s %s)', async (directoryDone, storageDone, heading) => {
    vi.spyOn(gateway.setup, 'status').mockResolvedValue({ authMode: 'ad', directoryDone, storageDone, adminDone: false })
    await openUnconfigured('/setup')
    await screen.findByRole('heading', { name: heading })
  })
  it('requires a successful transient credential test before saving', async () => {
    const { user } = await openFreshSetup()
    await user.click(screen.getByRole('button', { name: 'AD 연동' }))
    await screen.findByRole('heading', { name: 'AD 서버 등록' })
    fillDirectoryForm()
    expect(screen.getByRole('button', { name: 'AD 서버 등록' })).toBeDisabled()
    await passDirectoryTest(user)
    expect(screen.queryByLabelText(/바인드/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'AD 서버 등록' }))
    await screen.findByRole('heading', { name: '파일 저장 위치' })
  })
})
