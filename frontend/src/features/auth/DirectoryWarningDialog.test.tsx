import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import type { DirectoryWarning } from '../../shared/model/types'
import { DEFAULT_DEALS_URL_PATTERN } from '../../test/dealsUrl'
import { USER_ID } from '../../test/fake/seed/ids'
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
    const me = await gateway.auth.quickLogin(userId)
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
  it('shows the server message in a dialog on the first page after login', async () => {
    loginReturns(CONNECT_WARNING)
    const { user, location } = await openLogin()

    await signIn(user)

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    const popup = within(await dialog())
    expect(popup.getByText(CONNECT_WARNING.message)).toBeInTheDocument()
    expect(popup.getByRole('button', { name: '외부연동 설정으로 이동' })).toBeInTheDocument()
    expect(popup.getByRole('button', { name: '닫기' })).toBeInTheDocument()
  })

  it('shows the message of whichever stage the server reports', async () => {
    loginReturns(UNREADABLE_WARNING)
    const { user } = await openLogin()

    await signIn(user)

    expect(within(await dialog()).getByText(UNREADABLE_WARNING.message)).toBeInTheDocument()
  })

  it('goes to the integrations page and does not come back after the move', async () => {
    loginReturns(CONNECT_WARNING)
    const { user, location, goTo } = await openLogin()
    await signIn(user)
    const popup = within(await dialog())

    await user.click(popup.getByRole('button', { name: '외부연동 설정으로 이동' }))

    await waitFor(() => expect(location()).toBe('/admin/integrations'))
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
    goTo('/dashboard')
    goTo('/admin/integrations')
    await screen.findByRole('heading', { name: 'AD(LDAP) 서버 설정' })
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
  })

  it('closes with the close button and does not show again while moving around', async () => {
    loginReturns(CONNECT_WARNING)
    const { user, location, goTo } = await openLogin()
    await signIn(user)
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    const popup = within(await dialog())

    await user.click(popup.getByRole('button', { name: '닫기' }))

    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
    expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN) // 닫기만 하고 이동하지 않는다
    goTo('/dashboard')
    await screen.findByRole('navigation', { name: '주 메뉴' })
    goTo('/deals')
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
  })

  it('shows no dialog when the login response has no warning', async () => {
    loginReturns(null)
    const { user, location } = await openLogin()

    await signIn(user)

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByText('AD 연결 경고')).not.toBeInTheDocument()
  })

  it('shows no dialog when the session was not created by a login with a warning', async () => {
    await renderAt('/deals', { role: 'admin' })

    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(screen.queryByRole('dialog', { name: 'AD 연결 경고' })).not.toBeInTheDocument()
  })

  it('forgets a dismissed warning on logout so the next warning login shows it again', async () => {
    loginReturns(CONNECT_WARNING)
    const { user } = await openLogin()
    await signIn(user)
    await user.click(within(await dialog()).getByRole('button', { name: '닫기' }))
    await user.click(await screen.findByRole('button', { name: '로그아웃' }))
    await screen.findByRole('button', { name: '로그인' })
    loginReturns(UNREADABLE_WARNING)

    await signIn(user)

    expect(within(await dialog()).getByText(UNREADABLE_WARNING.message)).toBeInTheDocument()
  })

  it('does not show the previous warning after logging in again without one', async () => {
    loginReturns(CONNECT_WARNING)
    const { user } = await openLogin()
    await signIn(user)
    await user.click(within(await dialog()).getByRole('button', { name: '닫기' }))
    await user.click(await screen.findByRole('button', { name: '로그아웃' }))
    await screen.findByRole('button', { name: '로그인' })
    loginReturns(null)

    await signIn(user)

    await screen.findByRole('navigation', { name: '주 메뉴' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('keeps the warning out of the browser storage', async () => {
    loginReturns(CONNECT_WARNING)
    const { user } = await openLogin()
    await signIn(user)
    await dialog()

    const stored = JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage })
    expect(stored).not.toContain('호스트·포트·방화벽')
    expect(stored).not.toMatch(/directoryWarning|directory_warning/)
  })
})
