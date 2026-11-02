import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { openUserMenu } from '../../test/localAccounts'
import { renderAt } from '../../test/mockApp'

/** 상단 바 오른쪽 사용자 아이콘 메뉴 (local 계정 관리 AC-12). */
describe('사용자 아이콘 메뉴', () => {
  it('shows an icon button instead of the plain name text and logout button', async () => {
    await renderAt('/deals', { role: 'sales' })

    const trigger = await screen.findByRole('button', { name: '사용자 메뉴' })
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger.querySelector('svg')).not.toBeNull()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '로그아웃' })).not.toBeInTheDocument()
  })

  it('opens a menu with the name (role), 내 정보 and 로그아웃', async () => {
    const { user } = await renderAt('/deals', { role: 'sales' })

    const menu = await openUserMenu(user)

    expect(screen.getByRole('button', { name: '사용자 메뉴' })).toHaveAttribute('aria-expanded', 'true')
    expect(within(menu).getByText('김영업 (sales)')).toBeInTheDocument()
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual(['내 정보', '로그아웃'])
  })

  it('closes with Escape and gives the focus back to the icon button', async () => {
    const { user } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    await user.keyboard('{Escape}')

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '사용자 메뉴' })).toHaveFocus()
  })

  it('closes when the user clicks outside the menu', async () => {
    const { user } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    await user.click(screen.getByRole('navigation', { name: '주 메뉴' }))

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('toggles closed when the icon button is pressed again', async () => {
    const { user } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    await user.click(screen.getByRole('button', { name: '사용자 메뉴' }))

    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('moves to /me from 내 정보 and closes the menu', async () => {
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    await user.click(screen.getByRole('menuitem', { name: '내 정보' }))

    await waitFor(() => expect(location()).toBe('/me'))
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '내 정보' })).toBeInTheDocument()
  })

  it('keeps logging out working from the menu', async () => {
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    await user.click(screen.getByRole('menuitem', { name: '로그아웃' }))

    await waitFor(() => expect(location()).toBe('/login'))
  })

  it.each(['admin', 'sales', 'user'] as const)('is available to the %s role', async (role) => {
    await renderAt('/deals', { role })

    expect(await screen.findByRole('button', { name: '사용자 메뉴' })).toBeInTheDocument()
  })

  it('also works inside the opened mobile menu', async () => {
    const { user } = await renderAt('/deals', { role: 'sales' })
    await user.click(await screen.findByRole('button', { name: '메뉴 열기' }))

    const menu = await openUserMenu(user)

    expect(within(menu).getByRole('menuitem', { name: '내 정보' })).toBeInTheDocument()
  })
})
