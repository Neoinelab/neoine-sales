import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { DEFAULT_DEALS_URL_PATTERN } from '../../test/dealsUrl'

describe('Admin 공통 틀 (T-ADMIN-13)', () => {
  // Admin 틀은 제목과 서브 메뉴 4개를 보인다.
  // 테스트 코드: PL-063
  it('shows the title and the four sub menus', async () => {
    // when: /admin/users를 연다 (전제: BOSS)
    await renderAt('/admin/users', { role: 'admin' })
    // then: h1 "Admin > Settings"와 서브 메뉴 4개가 순서대로 보인다
    expect(await screen.findByRole('heading', { level: 1, name: 'Admin > Settings' })).toBeInTheDocument()
    const nav = within(screen.getByRole('navigation', { name: 'Admin 메뉴' }))
    expect(nav.getAllByRole('link').map((a) => a.textContent)).toEqual(['사용자 관리', 'Deal 관리', 'contacts 관리', '외부연동'])
  })

  // Admin 서브 메뉴는 현재 화면을 표시한다.
  // 테스트 코드: PL-064
  it.each([
    ['/admin/users', '사용자 관리'],
    ['/admin/deal', 'Deal 관리'],
    ['/admin/contacts', 'contacts 관리'],
    ['/admin/integrations', '외부연동'],
  ])('marks the current sub menu and shows its page at %s', async (url, label) => {
    // when: Admin 주소를 연다 (전제: BOSS)
    await renderAt(url, { role: 'admin' })
    // then: 그 서브 메뉴가 aria-current="page"이고 화면 제목(h2)이 보인다
    const nav = within(await screen.findByRole('navigation', { name: 'Admin 메뉴' }))
    expect(nav.getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByRole('heading', { level: 2, name: label })).toBeInTheDocument()
  })

  // Admin 서브 메뉴를 누르면 그 화면으로 이동한다.
  // 테스트 코드: PL-064
  it('moves between pages with the sub menu', async () => {
    // given: /admin/users를 연 BOSS
    const { user, location } = await renderAt('/admin/users', { role: 'admin' })
    // when: 외부연동을 누른다
    await user.click(await screen.findByRole('link', { name: '외부연동' }))
    // then: 주소가 /admin/integrations다
    expect(location()).toBe('/admin/integrations')
  })

  // sales·user는 Admin 화면에서 Deals 목록으로 가고 Admin 메뉴가 보이지 않는다.
  // 테스트 코드: PL-056
  it.each(['sales', 'user'] as const)('sends a %s user away from every Admin page (T-ADMIN-14)', async (role) => {
    // when: /admin/contacts를 연다 (전제: KIM 또는 VIEWER)
    const { location } = await renderAt('/admin/contacts', { role })
    // then: Deals 목록 주소가 되고 Admin 메뉴가 없다
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    expect(screen.queryByRole('navigation', { name: 'Admin 메뉴' })).not.toBeInTheDocument()
  })
})
