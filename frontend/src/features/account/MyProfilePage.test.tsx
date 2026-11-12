import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { ApiError } from '../../shared/api/problem'
import { SEED_PASSWORD } from '../../test/fake/seed/users'
import { openUserMenu, renderLocalAt } from '../../test/localAccounts'
import { renderAt } from '../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openMyPage(role: 'admin' | 'sales' | 'user' = 'sales') {
  const view = await renderLocalAt('/me', { role })
  await screen.findByRole('heading', { name: '내 정보' })
  return view
}

async function openMyPageInAd(role: 'admin' | 'sales' | 'user' = 'sales') {
  const view = await renderAt('/me', { role })
  await screen.findByRole('heading', { name: '내 정보' })
  return view
}

const input = (label: string) => screen.getByLabelText(label)

async function replace(user: Rendered['user'], label: string, text: string) {
  await user.clear(input(label))
  if (text) await user.type(input(label), text)
}

describe('내 정보 화면', () => {
  // 아이디·역할은 읽기 전용, 이름·이메일·전화는 편집 칸으로 보인다.
  // 테스트 코드: ME-038
  it('shows the id and role read-only and the editable profile', async () => {
    // when: /me를 연다 (전제: local 모드 sales(김영업)로 로그인)
    await openMyPage('sales')

    // then: 아이디 kim·역할 sales는 readonly, 이름 김영업·이메일·전화번호는 활성이다
    expect(input('아이디')).toHaveValue('kim')
    expect(input('아이디')).toHaveAttribute('readonly')
    expect(input('역할')).toHaveValue('sales')
    expect(input('역할')).toHaveAttribute('readonly')
    expect(input('이름')).toHaveValue('김영업')
    expect(input('이름')).toBeEnabled()
    expect(input('이메일')).toBeEnabled()
    expect(input('전화번호')).toBeEnabled()
  })

  // 세 역할 모두 편집 칸과 저장 버튼을 본다.
  // 테스트 코드: ME-038
  it.each(['admin', 'sales', 'user'] as const)('is open to the %s role', async (role) => {
    // when: /me를 연다 (전제: local 모드, 해당 역할로 로그인)
    await openMyPage(role)

    // then: 이름 칸이 활성이고 저장 버튼이 있다
    expect(input('이름')).toBeEnabled()
    expect(screen.getByRole('button', { name: '저장' })).toBeInTheDocument()
  })

  // 로그인하지 않고 /me를 열면 로그인 화면으로 간다.
  // 테스트 코드: ME-039
  it('redirects a visitor who is not signed in to the login page', async () => {
    // when: /me를 연다 (전제: 로그인하지 않았다)
    const { location } = await renderAt('/me', { role: null })

    // then: 주소가 /login이 된다
    await waitFor(() => expect(location()).toBe('/login'))
  })

  // 내 정보 조회가 실패하면 제목과 오류 배너만 보인다.
  // 테스트 코드: ME-040
  it('shows only the title and an error banner when the profile cannot be read', async () => {
    // given: 로그인했고 내 정보 조회가 500으로 실패한다
    vi.spyOn(gateway.me, 'profile').mockRejectedValue(
      rejectedWith(500, 'internal-error', '내 정보를 불러오지 못했습니다.'),
    )

    // when: /me를 연다
    await renderAt('/me', { role: 'sales' })

    // then: 제목과 alert 문구만 보이고 두 카드는 없다
    expect(await screen.findByRole('alert')).toHaveTextContent('내 정보를 불러오지 못했습니다.')
    expect(screen.getByRole('heading', { name: '내 정보' })).toBeInTheDocument()
    expect(screen.queryByLabelText('기본 정보')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '비밀번호 변경' })).not.toBeInTheDocument()
  })

  // 바뀐 칸이 없으면 저장 버튼이 비활성이다.
  // 테스트 코드: ME-041
  it('keeps the save button disabled until something changes', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    // when: 아무것도 고치지 않았다가 전화번호를 입력한다
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()
    await user.type(input('전화번호'), '02-123-4567')

    // then: 처음엔 비활성, 입력 뒤엔 활성이다
    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
  })

  // 바뀐 칸만 보내고 저장했습니다 안내를 보인다.
  // 테스트 코드: ME-042
  it('saves only the changed fields and shows a notice', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    const update = vi.spyOn(gateway.me, 'updateProfile')
    // when: 이름과 전화번호를 바꿔 저장한다
    await replace(user, '이름', '김새이름')
    await user.type(input('전화번호'), '010-9999-8888')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 안내가 보이고 요청은 한 번 이름·전화만 담았으며 저장된 이름이 바뀌었다
    expect(await screen.findByText('저장했습니다.')).toBeInTheDocument()
    expect(update).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith({ name: '김새이름', phone: '010-9999-8888' })
    expect((await gateway.me.profile()).name).toBe('김새이름')
  })

  // 이메일을 비우면 null을 보낸다.
  // 테스트 코드: ME-043
  it('clears the email by sending null', async () => {
    // given: local 모드로 /me를 열었다(이메일 있음)
    const { user } = await openMyPage()
    const update = vi.spyOn(gateway.me, 'updateProfile')
    // when: 이메일 칸을 비우고 저장한다
    await replace(user, '이메일', '')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 안내가 보이고 요청은 { email: null }, 저장된 이메일은 null이다
    await screen.findByText('저장했습니다.')
    expect(update).toHaveBeenCalledWith({ email: null })
    expect((await gateway.me.profile()).email).toBeNull()
  })

  // 저장 뒤 사용자 메뉴에 새 이름이 보인다.
  // 테스트 코드: ME-044
  it('shows the new name in the user menu after saving', async () => {
    // given: local 모드 sales로 /me에서 이름을 김새이름으로 저장했다
    const { user } = await openMyPage()
    await replace(user, '이름', '김새이름')
    await user.click(screen.getByRole('button', { name: '저장' }))
    await screen.findByText('저장했습니다.')

    // when: 사용자 메뉴를 연다
    await openUserMenu(user)

    // then: "김새이름 (sales)"가 보인다
    expect(await screen.findByText('김새이름 (sales)')).toBeInTheDocument()
  })

  // 서버가 값을 거절하면 서버 문구를 보이고 입력을 유지한다.
  // 테스트 코드: ME-045
  it('shows the server message for an invalid value and keeps the typed input', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    // when: 이메일을 not-an-email로 바꿔 저장한다
    await replace(user, '이메일', 'not-an-email')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 경고에 서버 문구, 이메일 칸은 그대로, 성공 안내는 없다
    expect(await screen.findByRole('alert')).toHaveTextContent('이메일 형식이 올바르지 않습니다.')
    expect(input('이메일')).toHaveValue('not-an-email')
    expect(screen.queryByText('저장했습니다.')).not.toBeInTheDocument()
  })

  // 이름을 비워 저장하면 서버의 이름 문구를 보인다.
  // 테스트 코드: ME-045
  it('refuses a blank name with the server message', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    // when: 이름을 비워 저장한다
    await replace(user, '이름', '')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 경고에 서버의 이름 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('이름은(는) 비어 있을 수 없습니다')
  })
})

describe('내 정보: AD 연동 모드', () => {
  // AD 모드에서는 이름·이메일이 비활성이고 안내와 함께 전화만 저장한다.
  // 테스트 코드: ME-046
  it('lets the user edit only the phone and explains that name and email come from AD', async () => {
    // given: AD 모드로 /me를 열었다
    const { user } = await openMyPageInAd()
    expect(input('이름')).toBeDisabled()
    expect(input('이메일')).toBeDisabled()
    expect(input('전화번호')).toBeEnabled()
    expect(screen.getByText(/이름·이메일은 AD에서 관리합니다/)).toBeInTheDocument()
    const update = vi.spyOn(gateway.me, 'updateProfile')

    // when: 전화번호를 넣어 저장한다
    await user.type(input('전화번호'), '010-1111-2222')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 안내가 보이고 요청은 { phone }만 담는다
    expect(await screen.findByText('저장했습니다.')).toBeInTheDocument()
    expect(update).toHaveBeenCalledWith({ phone: '010-1111-2222' })
  })

  // AD 모드에서는 비밀번호 변경 카드가 없다.
  // 테스트 코드: ME-047
  it('has no password section', async () => {
    // when: /me를 연다 (전제: AD 모드로 로그인)
    await openMyPageInAd()

    // then: 비밀번호 변경 제목과 현재 비밀번호 칸이 없다
    expect(screen.queryByRole('heading', { name: '비밀번호 변경' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('현재 비밀번호')).not.toBeInTheDocument()
  })
})

describe('내 정보: 비밀번호 변경', () => {
  async function fillPasswords(user: Rendered['user'], current: string, next: string, confirm = next) {
    await user.type(input('현재 비밀번호'), current)
    await user.type(input('새 비밀번호'), next)
    await user.type(input('새 비밀번호 확인'), confirm)
  }

  const submit = (user: Rendered['user']) => user.click(screen.getByRole('button', { name: '비밀번호 변경' }))

  // local 모드 비밀번호 변경 카드는 세 개의 비밀번호 칸을 가진다.
  // 테스트 코드: ME-048
  it('shows the section with three password fields in local mode', async () => {
    // when: /me를 연다 (전제: local 모드로 로그인)
    await openMyPage()

    // then: 제목이 있고 세 칸은 password 형식이며 autocomplete가 알맞다
    expect(screen.getByRole('heading', { name: '비밀번호 변경' })).toBeInTheDocument()
    for (const label of ['현재 비밀번호', '새 비밀번호', '새 비밀번호 확인']) {
      expect(input(label)).toHaveAttribute('type', 'password')
    }
    expect(input('현재 비밀번호')).toHaveAttribute('autocomplete', 'current-password')
    expect(input('새 비밀번호')).toHaveAttribute('autocomplete', 'new-password')
  })

  // 비밀번호를 바꾸면 칸을 비우고 다른 기기 로그인 종료를 알린다.
  // 테스트 코드: ME-049
  it('changes the password, clears the fields and says other devices were signed out', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    const change = vi.spyOn(gateway.me, 'changePassword')
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd')

    // when: "비밀번호 변경"을 누른다
    await submit(user)

    // then: 종료 안내, 요청 값 (시드, Fresh-passw0rd), 세 칸이 비어 있다
    expect(await screen.findByText(/다른 기기의 로그인이 종료되었습니다/)).toBeInTheDocument()
    expect(change).toHaveBeenCalledWith(SEED_PASSWORD, 'Fresh-passw0rd')
    expect(input('현재 비밀번호')).toHaveValue('')
    expect(input('새 비밀번호')).toHaveValue('')
    expect(input('새 비밀번호 확인')).toHaveValue('')
  })

  // 새 비밀번호 확인이 다르면 요청하지 않고 문구를 보인다.
  // 테스트 코드: ME-050
  it('does not submit when the confirmation differs', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    const change = vi.spyOn(gateway.me, 'changePassword')
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd', 'Fresh-passw0rX')

    // when: "비밀번호 변경"을 누른다
    await submit(user)

    // then: 불일치 경고가 보이고 변경 요청은 가지 않았다
    expect(await screen.findByRole('alert')).toHaveTextContent('새 비밀번호 확인이 일치하지 않습니다.')
    expect(change).not.toHaveBeenCalled()
  })

  // 현재 비밀번호가 틀리면 서버 문구를 보이고 칸을 비운다.
  // 테스트 코드: ME-051
  it('shows the wrong current password message next to the form and clears the secrets', async () => {
    // given: local 모드, 변경 요청이 422 "현재 비밀번호가 올바르지 않습니다."로 거절된다
    const { user } = await openMyPage()
    vi.spyOn(gateway.me, 'changePassword').mockRejectedValue(
      rejectedWith(422, 'invalid-value', '현재 비밀번호가 올바르지 않습니다.'),
    )
    await fillPasswords(user, 'wrong-password-1', 'Fresh-passw0rd')

    // when: "비밀번호 변경"을 누른다
    await submit(user)

    // then: 서버 문구가 보이고 칸은 비며 성공 안내는 없다
    expect(await screen.findByText('현재 비밀번호가 올바르지 않습니다.')).toBeInTheDocument()
    expect(input('현재 비밀번호')).toHaveValue('')
    expect(input('새 비밀번호')).toHaveValue('')
    expect(screen.queryByText(/다른 기기의 로그인이 종료되었습니다/)).not.toBeInTheDocument()
  })

  // 시도 제한에 걸리면 잠금 문구를 보인다.
  // 테스트 코드: ME-052
  it('shows the lock message when too many attempts were made', async () => {
    // given: local 모드, 변경 요청이 429로 거절된다
    const { user } = await openMyPage()
    vi.spyOn(gateway.me, 'changePassword').mockRejectedValue(
      rejectedWith(429, 'too-many-attempts', '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요'),
    )
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd')

    // when: "비밀번호 변경"을 누른다
    await submit(user)

    // then: 경고에 잠금 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인 시도가 너무 많습니다')
  })

  // 약한 새 비밀번호는 서버 문구를 보인다.
  // 테스트 코드: ME-053
  it('shows the server message for a weak new password', async () => {
    // given: local 모드로 /me를 열었다
    const { user } = await openMyPage()
    await fillPasswords(user, SEED_PASSWORD, 'short7!')

    // when: "비밀번호 변경"을 누른다
    await submit(user)

    // then: 경고에 서버의 길이 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다')
  })

  // 입력한 비밀번호가 mutation 캐시에 남지 않는다.
  // 테스트 코드: ME-054
  it('does not keep the typed passwords in the mutation cache', async () => {
    // given: local 모드로 /me에서 비밀번호를 Fresh-passw0rd로 바꿨다
    const { user, client } = await openMyPage()
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd')
    await submit(user)
    await screen.findByText(/다른 기기의 로그인이 종료되었습니다/)

    // when: mutation 캐시의 변수 전체를 문자열로 만든다
    const cached = JSON.stringify(
      client
        .getMutationCache()
        .getAll()
        .map((m) => m.state.variables),
    )

    // then: 새 비밀번호도 이전 비밀번호도 들어 있지 않다
    expect(cached).not.toContain('Fresh-passw0rd')
    expect(cached).not.toContain(SEED_PASSWORD)
  })
})

/** 서버 형식의 ApiError 하나를 만든다. */
function rejectedWith(status: number, kind: string, detail: string): ApiError {
  return new ApiError(status, { type: `https://sales.neoine.test/problems/${kind}`, title: kind, status, detail })
}
