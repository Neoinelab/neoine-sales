import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'

describe('상단 메뉴 순서 (계약관리 AC1)', () => {
  it.each(['admin', 'sales', 'user'] as const)('puts 계약관리 right after Deals for %s', async (role) => {
    await renderAt('/deals', { role })

    const nav = await screen.findByRole('navigation', { name: '주 메뉴' })

    const links = within(nav).getAllByRole('link')
    expect(links[0]).toHaveTextContent('Deals')
    expect(links[1]).toHaveTextContent('계약관리')
    expect(links[1]).toHaveAttribute('href', '/contracts')
  })
})
