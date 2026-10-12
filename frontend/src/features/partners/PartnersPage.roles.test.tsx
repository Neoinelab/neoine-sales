import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { asMe } from '../../test/authFixtures'
import { DETAIL_PARTNER, listPage } from '../../test/dealFixtures'
import { mockApi, renderApp, settled } from '../../test/utils'
import { PartnersPage } from './PartnersPage'

const routes = (role: 'admin' | 'sales' | 'user') => ({
  'GET /api/v1/auth/me': { body: asMe(role) },
  'GET /api/v1/partners': listPage([DETAIL_PARTNER]),
})

describe('PartnersPage write controls by role (UI-9)', () => {
  it('hides register, edit and delete from a viewer but still lists the partners', async () => {
    mockApi(routes('user'))
    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('한빛')
    await settled()

    expect(screen.queryByRole('button', { name: '파트너 등록' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })

  it.each(['sales', 'admin'] as const)('keeps register, edit and delete for %s', async (role) => {
    mockApi(routes(role))
    renderApp(<PartnersPage />, '/partners')

    expect(await screen.findByRole('button', { name: '파트너 등록' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '수정' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '삭제' })).toBeInTheDocument()
  })
})
