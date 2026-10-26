import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import { DEFAULT_DEALS_URL_PATTERN } from '../../test/dealsUrl'

describe('Admin 공통 틀 (T-ADMIN-13)', () => {
  it('shows the title and the four sub menus', async () => {
    await renderAt('/admin/users', { role: 'admin' })

    expect(await screen.findByRole('heading', { level: 1, name: 'Admin > Settings' })).toBeInTheDocument()
    const nav = within(screen.getByRole('navigation', { name: 'Admin 메뉴' }))
    expect(nav.getAllByRole('link').map((a) => a.textContent)).toEqual(['사용자 관리', 'Deal 관리', 'contacts 관리', '외부연동'])
  })

  it.each([
    ['/admin/users', '사용자 관리'],
    ['/admin/deal', 'Deal 관리'],
    ['/admin/contacts', 'contacts 관리'],
    ['/admin/integrations', '외부연동'],
  ])('marks the current sub menu and shows its page at %s', async (url, label) => {
    await renderAt(url, { role: 'admin' })

    const nav = within(await screen.findByRole('navigation', { name: 'Admin 메뉴' }))
    expect(nav.getByRole('link', { name: label })).toHaveAttribute('aria-current', 'page')
    expect(await screen.findByRole('heading', { level: 2, name: label })).toBeInTheDocument()
  })

  it('moves between pages with the sub menu', async () => {
    const { user, location } = await renderAt('/admin/users', { role: 'admin' })

    await user.click(await screen.findByRole('link', { name: '외부연동' }))

    expect(location()).toBe('/admin/integrations')
  })

  it.each(['sales', 'user'] as const)('sends a %s user away from every Admin page (T-ADMIN-14)', async (role) => {
    const { location } = await renderAt('/admin/contacts', { role })

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    expect(screen.queryByRole('navigation', { name: 'Admin 메뉴' })).not.toBeInTheDocument()
  })
})
