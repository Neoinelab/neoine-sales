import { defaultMock } from '../../test/fake/default'
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { DirectoryWarning } from '../../shared/model/types'
import { DEFAULT_DEALS_URL_PATTERN } from '../../test/dealsUrl'
import { USER_ID } from '../../test/fake/seed/ids'
import { logOutFromMenu } from '../../test/localAccounts'
import { renderAt } from '../../test/mockApp'

/**
 * AD가 답하지 못해 저장된 비밀번호로 들어온 admin에게 로그인 뒤 AD 오류 팝업을 보인다(AC15).
 * 경고는 로그인 응답(`directoryWarning`)에서만 오고, 닫거나 이동하면 다시 나오지 않으며,
 * 로그아웃하면 지워지고 브라우저 저장소에는 남지 않는다.
 */

afterEach(() => vi.restoreAllMocks())

const CONNECT_WARNING: DirectoryWarning = {
  stage: 'connect',
  message: 'AD 서버에 연결하지 못해 이전에 로그인한 비밀번호로 로그인했습니다. 호스트·포트·방화벽을 확인하세요.',
}
const UNREADABLE_WARNING: DirectoryWarning = {
  stage: 'credential_unreadable',
  message: '저장된 바인드 비밀번호를 읽을 수 없어(암호화 키 변경 여부 확인) 이전에 로그인한 비밀번호로 로그인했습니다.',
}

/** 로그인 응답이 주어진 경고를 싣는다. 세션은 시드 admin의 실제 mock 로그인으로 만든다. */
function loginReturns(warning: DirectoryWarning | null, userId: number = USER_ID.root) {
  return vi.spyOn(gateway.auth, 'login').mockImplementation(async () => {
    const me = await defaultMock.signInAs(userId)
    return { me, directoryWarning: warning }
  })
}

async function signIn(user: Awaited<ReturnType<typeof renderAt>>['user']) {
  await user.type(await screen.findByLabelText('아이디'), 'root')
  await user.type(screen.getByLabelText('비밀번호'), 'pw-root')
  await user.click(screen.getByRole('button', { name: '로그인' }))
}

async function openLogin() {
  const view = await renderAt('/login', { role: null })
  await screen.findByRole('button', { name: '로그인' })
  return view
}

const dialog = () => screen.findByRole('dialog', { name: 'AD 연결 경고' })

describe('로그인 뒤 admin AD 경고 팝업 (AC15)', () => {
  // 대체 로그인한 admin에게 로그인 직후 AD 연결 경고를 보인다.
  // 테스트 코드: AU-078
  it('shows the server message in a dialog on the first page after login', async () => {
    // given: 로그인 응답이 connect 경고를 싣는다
    loginReturns(CONNECT_WARNING)
    const { user, location } = await openLogin()

    // when: admin이 로그인한다
    await signIn(user)

    // then: Deals 목록에서 서버 문구와 두 버튼이 있는 'AD 연결 경고' 대화상자가 보인다
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    const popup = within(await dialog())
    expect(popup.getByText(CONNECT_WARNING.message)).toBeInTheDocument()
    expect(popup.getByRole('button', { name: '외부연동 설정으로 이동' })).toBeInTheDocument()
    expect(popup.getByRole('button', { name: '닫기' })).toBeInTheDocument()
  })

  // 서버가 알린 단계의 문구를 그대로 보인다.
  // 테스트 코드: AU-078
  it('shows the message of whichever stage the server reports', async () => {
    // given: 로그인 응답이 credential_unreadable 경고를 싣는다
    loginReturns(UNREADABLE_WARNING)
    const { user } = await openLogin()

    // when: admin이 로그인한다
    await signIn(user)

    // then: 그 단계의 서버 문구가 대화상자에 보인다
    expect(within(await dialog()).getByText(UNREADABLE_WARNING.message)).toBeInTheDocument()
  })

  // 경고에서 외부연동 설정으로 이동하면 다시 보이지 않는다.
  // 테스트 코드: AU-079
  it('goes to the integrations page and does not come back after the move', async () => {
    // given: 경고와 함께 로그인한 admin의 대화상자
    loginReturns(CONNECT_WARNING)
    const { user, location, goTo } = await openLogin()
    await signIn(user)
    const popup = within(await dialog())

    // when: '외부연동 설정으로 이동'을 누른다
    await user.click(popup.getByRole('button', { name: '외부연동 설정으로 이동' }))

    // then: 외부연동 화면으로 가고 대화상자가 닫히며 화면을 옮겨도 다시 보이지 않는다
    // 외부연동 화면은 lazy 청크라 처음 불러올 때 기본 1초를 넘길 수 있어 넉넉히 기다린다
    await waitFor(() => expect(location()).toBe('/admin/integrations'), { timeout: 10_000 })
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
    goTo('/dashboard')
    goTo('/admin/integrations')
    await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' }, { timeout: 10_000 })
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
  })

  // 경고를 닫으면 화면을 옮겨도 다시 보이지 않는다.
  // 테스트 코드: AU-080
  it('closes with the close button and does not show again while moving around', async () => {
    // given: 경고와 함께 로그인한 admin의 대화상자
    loginReturns(CONNECT_WARNING)
    const { user, location, goTo } = await openLogin()
    await signIn(user)
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    const popup = within(await dialog())

    // when: '닫기'를 누른다
    await user.click(popup.getByRole('button', { name: '닫기' }))

    // then: 닫히고 이동하지 않으며 다른 화면으로 옮겨도 다시 보이지 않는다
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
    expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN) // 닫기만 하고 이동하지 않는다
    goTo('/dashboard')
    await screen.findByRole('navigation', { name: '주 메뉴' })
    goTo('/deals')
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
  })

  // 경고 없는 로그인에는 경고가 없다.
  // 테스트 코드: AU-081
  it('shows no dialog when the login response has no warning', async () => {
    // given: 로그인 응답에 경고가 없다
    loginReturns(null)
    const { user, location } = await openLogin()

    // when: 로그인한다
    await signIn(user)

    // then: 대화상자가 없다
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText('AD 연결 경고')).not.toBeInTheDocument()
  })

  // 로그인 없이 연 세션에는 경고가 없다.
  // 테스트 코드: AU-081
  it('shows no dialog when the session was not created by a login with a warning', async () => {
    // when: 로그인 화면을 거치지 않고 admin 세션으로 Deals를 연다
    await renderAt('/deals', { role: 'admin' })

    await screen.findByRole('navigation', { name: '주 메뉴' })
    // then: 대화상자가 없다
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
  })

  // 로그아웃하면 경고가 지워지고 다음 로그인의 경고만 보인다.
  // 테스트 코드: AU-082
  it('forgets a dismissed warning on logout so the next warning login shows it again', async () => {
    // given: 경고를 닫고 로그아웃한 뒤 다음 로그인 응답은 다른 경고를 싣는다
    loginReturns(CONNECT_WARNING)
    const { user } = await openLogin()
    await signIn(user)
    await user.click(within(await dialog()).getByRole('button', { name: '닫기' }))
    await logOutFromMenu(user)
    await screen.findByRole('button', { name: '로그인' })
    loginReturns(UNREADABLE_WARNING)

    // when: 다시 로그인한다
    await signIn(user)

    // then: 이전 경고가 아닌 새 경고가 보인다
    expect(within(await dialog()).getByText(UNREADABLE_WARNING.message)).toBeInTheDocument()
  })

  // 경고 없이 다시 로그인하면 이전 경고는 보이지 않는다.
  // 테스트 코드: AU-082
  it('does not show the previous warning after logging in again without one', async () => {
    // given: 경고를 닫고 로그아웃했으며 다음 로그인 응답에는 경고가 없다
    loginReturns(CONNECT_WARNING)
    const { user } = await openLogin()
    await signIn(user)
    await user.click(within(await dialog()).getByRole('button', { name: '닫기' }))
    await logOutFromMenu(user)
    await screen.findByRole('button', { name: '로그인' })
    loginReturns(null)

    // when: 다시 로그인한다
    await signIn(user)

    // then: 대화상자가 없다
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 경고는 브라우저 저장소에 남지 않는다.
  // 테스트 코드: AU-083
  it('keeps the warning out of the browser storage', async () => {
    // given: 경고와 함께 로그인한 admin의 대화상자
    loginReturns(CONNECT_WARNING)
    const { user } = await openLogin()
    await signIn(user)
    // when: 대화상자가 떠 있는 동안 저장소를 본다
    await dialog()

    // then: localStorage·sessionStorage에 경고 문구가 없다
    const stored = JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage })
    expect(stored).not.toContain('호스트·포트·방화벽')
    expect(stored).not.toMatch(/directoryWarning|directory_warning/)
  })
})
