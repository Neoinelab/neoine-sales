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

describe('내 정보 화면 (AC-9·10·12)', () => {
  it('shows the id and role read-only and the editable profile', async () => {
    await openMyPage('sales')

    expect(input('아이디')).toHaveValue('kim')
    expect(input('아이디')).toHaveAttribute('readonly')
    expect(input('역할')).toHaveValue('sales')
    expect(input('역할')).toHaveAttribute('readonly')
    expect(input('이름')).toHaveValue('김영업')
    expect(input('이름')).toBeEnabled()
    expect(input('이메일')).toBeEnabled()
    expect(input('전화번호')).toBeEnabled()
  })

  it.each(['admin', 'sales', 'user'] as const)('is open to the %s role', async (role) => {
    await openMyPage(role)

    expect(input('이름')).toBeEnabled()
    expect(screen.getByRole('button', { name: '저장' })).toBeInTheDocument()
  })

  it('redirects a visitor who is not signed in to the login page', async () => {
    const { location } = await renderAt('/me', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })

  it('keeps the save button disabled until something changes', async () => {
    const { user } = await openMyPage()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()

    await user.type(input('전화번호'), '02-123-4567')

    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
  })

  it('saves only the changed fields and shows a notice', async () => {
    const { user } = await openMyPage()
    const update = vi.spyOn(gateway.me, 'updateProfile')
    await replace(user, '이름', '김새이름')
    await user.type(input('전화번호'), '010-9999-8888')

    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByText('저장했습니다.')).toBeInTheDocument()
    expect(update).toHaveBeenCalledTimes(1)
    expect(update).toHaveBeenCalledWith({ name: '김새이름', phone: '010-9999-8888' })
    expect((await gateway.me.profile()).name).toBe('김새이름')
  })

  it('clears the email and the phone by sending null', async () => {
    const { user } = await openMyPage()
    const update = vi.spyOn(gateway.me, 'updateProfile')
    await replace(user, '이메일', '')

    await user.click(screen.getByRole('button', { name: '저장' }))

    await screen.findByText('저장했습니다.')
    expect(update).toHaveBeenCalledWith({ email: null })
    expect((await gateway.me.profile()).email).toBeNull()
  })

  it('shows the new name in the user menu after saving', async () => {
    const { user } = await openMyPage()
    await replace(user, '이름', '김새이름')
    await user.click(screen.getByRole('button', { name: '저장' }))
    await screen.findByText('저장했습니다.')

    await openUserMenu(user)

    expect(await screen.findByText('김새이름 (sales)')).toBeInTheDocument()
  })

  it('shows the server message for an invalid value and keeps the typed input', async () => {
    const { user } = await openMyPage()
    await replace(user, '이메일', 'not-an-email')

    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이메일 형식이 올바르지 않습니다.')
    expect(input('이메일')).toHaveValue('not-an-email')
    expect(screen.queryByText('저장했습니다.')).not.toBeInTheDocument()
  })

  it('refuses a blank name with the server message', async () => {
    const { user } = await openMyPage()
    await replace(user, '이름', '')

    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이름')
  })
})

describe('내 정보: AD 연동 모드', () => {
  it('lets the user edit only the phone and explains that name and email come from AD', async () => {
    const { user } = await openMyPageInAd()

    expect(input('이름')).toBeDisabled()
    expect(input('이메일')).toBeDisabled()
    expect(input('전화번호')).toBeEnabled()
    expect(screen.getByText(/이름·이메일은 AD에서 관리합니다/)).toBeInTheDocument()
    const update = vi.spyOn(gateway.me, 'updateProfile')
    await user.type(input('전화번호'), '010-1111-2222')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByText('저장했습니다.')).toBeInTheDocument()
    expect(update).toHaveBeenCalledWith({ phone: '010-1111-2222' })
  })

  it('has no password section', async () => {
    await openMyPageInAd()

    expect(screen.queryByRole('heading', { name: '비밀번호 변경' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('현재 비밀번호')).not.toBeInTheDocument()
  })
})

describe('내 정보: 비밀번호 변경 (AC-11)', () => {
  async function fillPasswords(user: Rendered['user'], current: string, next: string, confirm = next) {
    await user.type(input('현재 비밀번호'), current)
    await user.type(input('새 비밀번호'), next)
    await user.type(input('새 비밀번호 확인'), confirm)
  }

  const submit = (user: Rendered['user']) => user.click(screen.getByRole('button', { name: '비밀번호 변경' }))

  it('shows the section with three password fields in local mode', async () => {
    await openMyPage()

    expect(screen.getByRole('heading', { name: '비밀번호 변경' })).toBeInTheDocument()
    for (const label of ['현재 비밀번호', '새 비밀번호', '새 비밀번호 확인']) {
      expect(input(label)).toHaveAttribute('type', 'password')
    }
    expect(input('현재 비밀번호')).toHaveAttribute('autocomplete', 'current-password')
    expect(input('새 비밀번호')).toHaveAttribute('autocomplete', 'new-password')
  })

  it('changes the password, clears the fields and says other devices were signed out', async () => {
    const { user } = await openMyPage()
    const change = vi.spyOn(gateway.me, 'changePassword')
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd')

    await submit(user)

    expect(await screen.findByText(/다른 기기의 로그인이 종료되었습니다/)).toBeInTheDocument()
    expect(change).toHaveBeenCalledWith(SEED_PASSWORD, 'Fresh-passw0rd')
    expect(input('현재 비밀번호')).toHaveValue('')
    expect(input('새 비밀번호')).toHaveValue('')
    expect(input('새 비밀번호 확인')).toHaveValue('')
  })

  it('does not submit when the confirmation differs', async () => {
    const { user } = await openMyPage()
    const change = vi.spyOn(gateway.me, 'changePassword')
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd', 'Fresh-passw0rX')

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('새 비밀번호 확인이 일치하지 않습니다.')
    expect(change).not.toHaveBeenCalled()
  })

  it('shows the wrong current password message next to the form and clears the secrets', async () => {
    const { user } = await openMyPage()
    vi.spyOn(gateway.me, 'changePassword').mockRejectedValue(
      rejectedWith(422, 'invalid-value', '현재 비밀번호가 올바르지 않습니다.'),
    )
    await fillPasswords(user, 'wrong-password-1', 'Fresh-passw0rd')

    await submit(user)

    expect(await screen.findByText('현재 비밀번호가 올바르지 않습니다.')).toBeInTheDocument()
    expect(input('현재 비밀번호')).toHaveValue('')
    expect(input('새 비밀번호')).toHaveValue('')
    expect(screen.queryByText(/다른 기기의 로그인이 종료되었습니다/)).not.toBeInTheDocument()
  })

  it('shows the lock message when too many attempts were made', async () => {
    const { user } = await openMyPage()
    vi.spyOn(gateway.me, 'changePassword').mockRejectedValue(
      rejectedWith(429, 'too-many-attempts', '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요'),
    )
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd')

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인 시도가 너무 많습니다')
  })

  it('shows the server message for a weak new password', async () => {
    const { user } = await openMyPage()
    await fillPasswords(user, SEED_PASSWORD, 'short7!')

    await submit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('비밀번호는 8자 이상이어야 합니다.')
  })

  it('does not keep the typed passwords in the mutation cache', async () => {
    const { user, client } = await openMyPage()
    await fillPasswords(user, SEED_PASSWORD, 'Fresh-passw0rd')
    await submit(user)
    await screen.findByText(/다른 기기의 로그인이 종료되었습니다/)

    const cached = JSON.stringify(
      client
        .getMutationCache()
        .getAll()
        .map((m) => m.state.variables),
    )

    expect(cached).not.toContain('Fresh-passw0rd')
    expect(cached).not.toContain(SEED_PASSWORD)
  })
})

/** 서버 형식의 ApiError 하나를 만든다. */
function rejectedWith(status: number, kind: string, detail: string): ApiError {
  return new ApiError(status, { type: `https://sales.neoine.test/problems/${kind}`, title: kind, status, detail })
}
