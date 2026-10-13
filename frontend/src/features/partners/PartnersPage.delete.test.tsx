import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { asMe } from '../../test/authFixtures'
import { DETAIL_PARTNER, listPage } from '../../test/dealFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { PartnersPage } from './PartnersPage'

describe('PartnersPage delete', () => {
  it('warns that deletion is irreversible and blocked by linked deals, and does nothing when declined', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: asMe('admin') },
      'GET /api/v1/partners': listPage([DETAIL_PARTNER]),
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderApp(<PartnersPage />, '/partners')

    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('복구할 수 없'))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('연결된 Deal이 있으면 삭제할 수 없습니다'))
    expect(requests.some((r) => r.method === 'DELETE')).toBe(false)
  })

  it('shows the server message when a partner is referenced by deals', async () => {
    const detail = '이 파트너를 참조하는 Deal이 있어 삭제할 수 없습니다: p-1'
    mockApi({
      'GET /api/v1/auth/me': { body: asMe('admin') },
      'GET /api/v1/partners': listPage([DETAIL_PARTNER]),
      [`DELETE /api/v1/partners/${DETAIL_PARTNER.id}`]: problem(409, 'invalid-state', detail),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<PartnersPage />, '/partners')

    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.getByText('한빛')).toBeInTheDocument()
  })
})
