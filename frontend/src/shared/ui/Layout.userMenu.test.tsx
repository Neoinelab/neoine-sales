import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { openUserMenu } from '../../test/localAccounts'
import { renderAt } from '../../test/mockApp'

/** 상단 바 오른쪽 사용자 아이콘 메뉴 (내 정보 ME-R1, ME-UC1). */
describe('사용자 아이콘 메뉴', () => {
  // 상단 바에는 사용자 아이콘 버튼만 있고 메뉴는 닫혀 있다.
  // 테스트 코드: ME-032
  it('shows an icon button instead of the plain name text and logout button', async () => {
    // when: /deals를 연다
    await renderAt('/deals', { role: 'sales' })

    // then: 사용자 메뉴 버튼은 닫혀 있고 svg를 가지며, 메뉴와 로그아웃 버튼은 보이지 않는다
    const trigger = await screen.findByRole('button', { name: '사용자 메뉴' })
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger.querySelector('svg')).not.toBeNull()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '로그아웃' })).not.toBeInTheDocument()
  })

  // 메뉴를 열면 이름(역할)과 내 정보·로그아웃이 순서대로 보인다.
  // 테스트 코드: ME-033
  it('opens a menu with the name (role), 내 정보 and 로그아웃', async () => {
    // given: sales 사용자 김영업으로 로그인해 /deals에 있다
    const { user } = await renderAt('/deals', { role: 'sales' })

    // when: 사용자 메뉴 버튼을 누른다
    const menu = await openUserMenu(user)

    // then: 열림 표시, "김영업 (sales)", 항목 순서 [내 정보, 로그아웃]
    expect(screen.getByRole('button', { name: '사용자 메뉴' })).toHaveAttribute('aria-expanded', 'true')
    expect(within(menu).getByText('김영업 (sales)')).toBeInTheDocument()
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual(['내 정보', '로그아웃'])
  })

  // Esc를 누르면 메뉴가 닫히고 포커스가 아이콘 버튼으로 돌아온다.
  // 테스트 코드: ME-034
  it('closes with Escape and gives the focus back to the icon button', async () => {
    // given: 사용자 메뉴가 열려 있다
    const { user } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 메뉴가 닫히고 포커스는 사용자 메뉴 버튼에 있다
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '사용자 메뉴' })).toHaveFocus()
  })

  // 메뉴 바깥을 누르면 닫힌다.
  // 테스트 코드: ME-034
  it('closes when the user clicks outside the menu', async () => {
    // given: 사용자 메뉴가 열려 있다
    const { user } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    // when: 주 메뉴(바깥)를 누른다
    await user.click(screen.getByRole('navigation', { name: '주 메뉴' }))

    // then: 메뉴가 닫힌다
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  // 아이콘 버튼을 다시 누르면 닫힌다.
  // 테스트 코드: ME-034
  it('toggles closed when the icon button is pressed again', async () => {
    // given: 사용자 메뉴가 열려 있다
    const { user } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    // when: 아이콘 버튼을 다시 누른다
    await user.click(screen.getByRole('button', { name: '사용자 메뉴' }))

    // then: 메뉴가 닫힌다
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  // 내 정보를 고르면 /me로 이동하고 메뉴가 닫힌다.
  // 테스트 코드: ME-035
  it('moves to /me from 내 정보 and closes the menu', async () => {
    // given: /deals에서 사용자 메뉴가 열려 있다
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    // when: "내 정보" 항목을 누른다
    await user.click(screen.getByRole('menuitem', { name: '내 정보' }))

    // then: 주소가 /me, 메뉴는 닫히고 제목 "내 정보"가 보인다
    await waitFor(() => expect(location()).toBe('/me'))
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: '내 정보' })).toBeInTheDocument()
  })

  // 로그아웃을 고르면 /login으로 간다.
  // 테스트 코드: ME-036
  it('keeps logging out working from the menu', async () => {
    // given: /deals에서 사용자 메뉴가 열려 있다
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    await openUserMenu(user)

    // when: "로그아웃" 항목을 누른다
    await user.click(screen.getByRole('menuitem', { name: '로그아웃' }))

    // then: 주소가 /login이 된다
    await waitFor(() => expect(location()).toBe('/login'))
  })

  // 세 역할 모두 사용자 메뉴 버튼을 가진다.
  // 테스트 코드: ME-037
  it.each(['admin', 'sales', 'user'] as const)('is available to the %s role', async (role) => {
    // when: /deals를 연다
    await renderAt('/deals', { role })

    // then: 사용자 메뉴 버튼이 있다
    expect(await screen.findByRole('button', { name: '사용자 메뉴' })).toBeInTheDocument()
  })

  // 모바일 메뉴를 연 상태에서도 같은 사용자 메뉴를 쓴다.
  // 테스트 코드: ME-037
  it('also works inside the opened mobile menu', async () => {
    // given: sales로 로그인해 "메뉴 열기"로 모바일 메뉴를 열었다
    const { user } = await renderAt('/deals', { role: 'sales' })
    await user.click(await screen.findByRole('button', { name: '메뉴 열기' }))

    // when: 사용자 메뉴를 연다
    const menu = await openUserMenu(user)

    // then: "내 정보" 항목이 있다
    expect(within(menu).getByRole('menuitem', { name: '내 정보' })).toBeInTheDocument()
  })
})
