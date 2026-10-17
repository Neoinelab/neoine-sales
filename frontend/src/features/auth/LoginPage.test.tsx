import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'

async function openLogin() {
  const view = await renderAt('/login', { role: null })
  await screen.findByRole('button', { name: '로그인' })
  return view
}

async function fill(user: Awaited<ReturnType<typeof renderAt>>['user'], loginId: string, password: string) {
  if (loginId) await user.type(screen.getByLabelText('아이디'), loginId)
  if (password) await user.type(screen.getByLabelText('비밀번호'), password)
}

describe('로그인 화면 (계획 6.1, T-SHELL-08)', () => {
  it('shows the id and password form, the three role quick logins without any-password guidance', async () => {
    await openLogin()
    expect(screen.getByLabelText('아이디')).toBeVisible()
    expect(screen.getByLabelText('비밀번호')).toBeVisible()
    const quick = within(screen.getByRole('region', { name: '빠른 로그인' }))
    expect(quick.getAllByRole('button').map((b) => b.textContent)).toEqual(['관리자', '영업', '조회자'])
    for (const person of ['최관리', '김영업', '박영업', '한조회']) {
      expect(screen.queryByText(new RegExp(person))).not.toBeInTheDocument()
    }
    expect(screen.queryByText(/아무 비밀번호나/)).not.toBeInTheDocument()
  })

  it('asks for both values when they are empty', async () => {
    const { user } = await openLogin()
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('아이디와 비밀번호를 입력하세요.')
  })

  it('asks for both values when only the id is filled', async () => {
    const { user } = await openLogin()
    await fill(user, 'kim', '')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('아이디와 비밀번호를 입력하세요.')
  })

  it('shows the fixed failure message for an unknown id and clears only the password', async () => {
    const { user, location } = await openLogin()
    await fill(user, 'nobody', 'secret')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('아이디 또는 비밀번호가 올바르지 않습니다.')
    expect(screen.getByLabelText('비밀번호')).toHaveValue('')
    expect(screen.getByLabelText('아이디')).toHaveValue('nobody')
    expect(location()).toBe('/login')
  })

  it('refuses a resigned user', async () => {
    const { user, location } = await openLogin()
    await fill(user, 'old', 'secret')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('퇴사한 사용자는 로그인할 수 없습니다.')
    expect(location()).toBe('/login')
  })

  it('accepts any password for a known id and moves to the deals list', async () => {
    const { user, location } = await openLogin()
    await fill(user, 'kim', 'whatever')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    await waitFor(() => expect(location()).toBe('/deals'))
    expect(await screen.findByText('김영업 (sales)')).toBeVisible()
  })

  it.each([
    ['관리자', '최관리 (admin)'],
    ['영업', '김영업 (sales)'],
    ['조회자', '한조회 (user)'],
  ])('signs in with the quick login %s by its role', async (button, shown) => {
    const { user, location } = await openLogin()
    await user.click(screen.getByRole('button', { name: button }))
    await waitFor(() => expect(location()).toBe('/deals'))
    expect(await screen.findByText(shown)).toBeVisible()
  })

  it('goes to the main page when already signed in', async () => {
    const { location } = await renderAt('/login', { role: 'sales' })
    await waitFor(() => expect(location()).toBe('/deals'))
  })

  it('does not keep the typed password in the mutation cache, on success or failure', async () => {
    const { user, client, location } = await openLogin()
    await fill(user, 'nobody', 'pw-secret-1')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    await screen.findByRole('alert')
    await user.clear(screen.getByLabelText('아이디'))
    await user.type(screen.getByLabelText('아이디'), 'kim')
    await user.type(screen.getByLabelText('비밀번호'), 'pw-secret-2')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    await waitFor(() => expect(location()).toBe('/deals'))
    await waitFor(() => {
      const kept = JSON.stringify(client.getMutationCache().getAll().map((m) => m.state.variables))
      expect(kept).not.toContain('pw-secret-1')
      expect(kept).not.toContain('pw-secret-2')
    })
  })
})
