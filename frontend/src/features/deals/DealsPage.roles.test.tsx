import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { asMe } from '../../test/authFixtures'
import { DETAIL_CUSTOMER, DETAIL_DEAL, listPage } from '../../test/dealFixtures'
import { mockApi, problem, renderApp, settled } from '../../test/utils'
import { DealsPage } from './DealsPage'

const routes = (role: 'admin' | 'sales' | 'user') => ({
  'GET /api/v1/auth/me': { body: asMe(role) },
  'GET /api/v1/deals': listPage([DETAIL_DEAL]),
  'GET /api/v1/customers': listPage([DETAIL_CUSTOMER], 200),
})

afterEach(() => vi.restoreAllMocks())

describe('DealsPage write controls by role (UI-9)', () => {
  it('hides register, edit and delete from a viewer but still lists the deals', async () => {
    mockApi(routes('user'))
    renderApp(<DealsPage />, '/deals')
    await screen.findByText('DEAL-001')
    await settled()

    expect(screen.queryByRole('button', { name: '딜 등록' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'DEAL-001' })).toBeInTheDocument()
  })

  it.each(['sales', 'admin'] as const)('keeps register, edit and delete for %s', async (role) => {
    mockApi(routes(role))
    renderApp(<DealsPage />, '/deals')

    expect(await screen.findByRole('button', { name: '딜 등록' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '수정' })).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '삭제' })).toBeInTheDocument()
  })

  it('shows the permission message of a 403 from the server (UI-10)', async () => {
    mockApi({
      ...routes('sales'),
      'DELETE /api/v1/deals/d-1': problem(403, 'forbidden', '조회 전용 계정은 이 작업을 할 수 없습니다. 관리자에게 문의하세요.'),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<DealsPage />, '/deals')

    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('조회 전용 계정은 이 작업을 할 수 없습니다. 관리자에게 문의하세요.')
    expect(alert).not.toHaveTextContent(/forbidden/i)
  })
})
