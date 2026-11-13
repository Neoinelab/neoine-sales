import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { keys } from '../../data/queryKeys'
import { gateway } from '../../gateway'
import { defaultDealsUrlPattern } from '../../test/dealsUrl'
import { SEED_PASSWORD } from '../../test/fake/seed/users'
import { renderAt } from '../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
})

const FAILED = '아이디 또는 비밀번호가 올바르지 않습니다'

async function openLogin() {
  const view = await renderAt('/login', { role: null })
  await screen.findByRole('button', { name: '로그인' })
  return view
}

async function fill(user: Awaited<ReturnType<typeof renderAt>>['user'], loginId: string, password: string) {
  if (loginId) await user.type(screen.getByLabelText('아이디'), loginId)
  if (password) await user.type(screen.getByLabelText('비밀번호'), password)
}

/** 응답을 직접 풀어 줄 수 있게 미뤄 두는 Promise. */
function deferred() {
  let release: () => void = () => {}
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  return { gate, release }
}

describe('로그인 화면 (AU)', () => {
  // 로그인 화면은 아이디·비밀번호 폼과 로그인 버튼만 보인다.
  // 테스트 코드: AU-067
  it('shows the id and password form, no quick login and no any-password guidance', async () => {
    // when: 로그인하지 않은 채 로그인 화면을 연다
    await openLogin()

    // then: 아이디·비밀번호 칸과 "로그인" 버튼 하나뿐이고 빠른 로그인·아무 비밀번호 안내가 없다
    expect(screen.getByLabelText('아이디')).toBeVisible()
    expect(screen.getByLabelText('비밀번호')).toBeVisible()
    expect(screen.queryByRole('region', { name: '빠른 로그인' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['로그인'])
    for (const person of ['최관리', '김영업', '박영업', '한조회']) {
      expect(screen.queryByText(new RegExp(person))).not.toBeInTheDocument()
    }
    expect(screen.queryByText(/아무 비밀번호나/)).not.toBeInTheDocument()
  })

  // 인증 설정을 읽는 동안 "불러오는 중…"만 보이고 읽고 나면 폼이 보인다.
  // 테스트 코드: AU-068
  it('shows only the loading text while the auth config is being read', async () => {
    // given: 인증 설정 응답이 아직 오지 않았다
    const original = gateway.auth.config.bind(gateway.auth)
    const pending = deferred()
    vi.spyOn(gateway.auth, 'config').mockImplementation(async () => {
      await pending.gate
      return original()
    })

    // when: 로그인 화면을 연다
    await renderAt('/login', { role: null })

    // then: "불러오는 중…"만 보이고 폼은 없다. 응답이 오면 폼이 나타난다
    expect(await screen.findByText('불러오는 중…')).toBeVisible()
    expect(screen.queryByLabelText('아이디')).not.toBeInTheDocument()
    pending.release()
    expect(await screen.findByRole('button', { name: '로그인' })).toBeVisible()
    expect(screen.queryByText('불러오는 중…')).not.toBeInTheDocument()
  })

  // 이미 로그인했으면 로그인 화면에서 Deals 목록으로 간다.
  // 테스트 코드: AU-070
  it('goes to the main page when already signed in', async () => {
    // when: 로그인 화면 주소를 연다 (전제: sales로 로그인한 상태)
    const { location } = await renderAt('/login', { role: 'sales' })

    // then: Deals 목록으로 바뀐다
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('sales')))
  })

  // 로그인에 성공하면 Deals 목록으로 가고 내 정보가 갱신된다.
  // 테스트 코드: AU-071
  it('moves to the deals list and refreshes the user after a successful login', async () => {
    // given: 로그인 화면과 등록된 사용자 kim
    const { user, location, client } = await openLogin()

    // when: 아이디와 올바른 비밀번호를 내고 로그인한다
    await fill(user, 'kim', SEED_PASSWORD)
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: Deals 목록으로 가고 내 정보 캐시가 kim으로 바뀐다
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('sales')))
    expect(client.getQueryData(keys.me)).toMatchObject({ loginId: 'kim', name: '김영업', role: 'sales' })
  })

  // 로그인에 실패하면 서버 문구를 보이고 비밀번호만 비운다.
  // 테스트 코드: AU-072
  it('shows the server message for a failed login and clears only the password', async () => {
    // given: 로그인 화면
    const { user, location } = await openLogin()

    // when: 없는 아이디로 로그인한다
    await fill(user, 'nobody', 'secret')
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 서버의 공통 실패 문구(마침표 없음)가 배너에 보이고 비밀번호만 비워지며 로그인 화면에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent(new RegExp(`^${FAILED}$`))
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('아이디')).toHaveValue('nobody')
    expect(location()).toBe('/login')
  })

  // 빈 칸으로 제출해도 화면이 따로 검사하지 않고 서버 판정 문구를 보인다.
  // 테스트 코드: AU-073
  it('shows the server verdict for empty fields instead of checking them on the screen', async () => {
    // given: 아무것도 채우지 않은 로그인 화면
    const login = vi.spyOn(gateway.auth, 'login')
    const { user, location } = await openLogin()

    // when: 그대로 로그인한다
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 요청이 서버로 가고 서버의 공통 실패 문구가 보이며 로그인 화면에 머문다
    expect(await screen.findByRole('alert')).toHaveTextContent(new RegExp(`^${FAILED}$`))
    expect(login).toHaveBeenCalledWith('', '')
    expect(location()).toBe('/login')
  })

  // 아이디만 채우고 제출해도 같은 서버 문구다.
  // 테스트 코드: AU-073
  it('shows the same server verdict when only the id is filled', async () => {
    // given: 로그인 화면
    const { user } = await openLogin()

    // when: 아이디만 채우고 로그인한다
    await fill(user, 'kim', '')
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 서버의 공통 실패 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent(new RegExp(`^${FAILED}$`))
  })

  // 퇴사자 로그인도 다른 실패와 같은 문구다.
  // 테스트 코드: AU-074
  it('refuses a resigned user with the same message as any other failure', async () => {
    // given: 로그인 화면과 퇴사 처리된 사용자 old
    const { user, location } = await openLogin()

    // when: old가 올바른 비밀번호로 로그인한다
    await fill(user, 'old', SEED_PASSWORD)
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 공통 실패 문구이고(퇴사 안내가 아니다) 로그인 화면에 머문다
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(new RegExp(`^${FAILED}$`))
    expect(alert).not.toHaveTextContent('퇴사')
    expect(location()).toBe('/login')
  })

  // 아이디 앞뒤 공백은 지워서 보내고 비밀번호는 그대로 보낸다.
  // 테스트 코드: AU-075
  it('trims the surrounding spaces of the id but sends the password as typed', async () => {
    // given: 로그인 화면
    const login = vi.spyOn(gateway.auth, 'login')
    const { user, location } = await openLogin()

    // when: 앞뒤에 공백이 있는 아이디로 로그인한다
    await fill(user, '  kim  ', SEED_PASSWORD)
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 공백 없는 아이디와 입력 그대로의 비밀번호가 요청되고 Deals 목록으로 간다
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('sales')))
    expect(login).toHaveBeenCalledWith('kim', SEED_PASSWORD)
  })

  // 요청 중에는 로그인 버튼이 비활성이다.
  // 테스트 코드: AU-076
  it('disables the login button while the request is in flight', async () => {
    // given: 응답이 늦는 로그인 요청
    const original = gateway.auth.login.bind(gateway.auth)
    const pending = deferred()
    vi.spyOn(gateway.auth, 'login').mockImplementation(async (loginId, password) => {
      await pending.gate
      return original(loginId, password)
    })
    const { user, location } = await openLogin()
    await fill(user, 'kim', SEED_PASSWORD)

    // when: 로그인을 누른다
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 응답이 오기 전에는 버튼이 비활성이고, 응답이 오면 Deals 목록으로 간다
    await waitFor(() => expect(screen.getByRole('button', { name: '로그인' })).toBeDisabled())
    pending.release()
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('sales')))
  })

  // 입력한 비밀번호는 성공이든 실패든 요청 캐시에 남지 않는다.
  // 테스트 코드: AU-077
  it('does not keep the typed password in the mutation cache, on success or failure', async () => {
    // given: 로그인 화면
    const { user, client, location } = await openLogin()

    // when: 먼저 틀리게, 그 다음 올바르게 로그인한다
    await fill(user, 'nobody', 'pw-secret-1')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    await screen.findByRole('alert')
    await user.clear(screen.getByLabelText('아이디'))
    await user.type(screen.getByLabelText('아이디'), 'kim')
    await user.type(screen.getByLabelText('비밀번호'), SEED_PASSWORD)
    await user.click(screen.getByRole('button', { name: '로그인' }))
    await waitFor(() => expect(location()).toMatch(defaultDealsUrlPattern('sales')))

    // then: 요청 캐시의 변수에 어느 비밀번호도 남아 있지 않다
    await waitFor(() => {
      const kept = JSON.stringify(client.getMutationCache().getAll().map((m) => m.state.variables))
      expect(kept).not.toContain('pw-secret-1')
      expect(kept).not.toContain(SEED_PASSWORD)
    })
  })
})
