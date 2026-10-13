import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, problem, renderApp } from '../../test/utils'
import { CustomersPage } from './CustomersPage'

const CUSTOMER = {
  id: 'c-1',
  company_name: '네오인',
  contact_name: '김철수',
  contact_title: '팀장',
  email: 'kim@neoine.example',
  phone: '010-1234-5678',
  employee_count: 120,
  notes: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('CustomersPage', () => {
  it('warns that deletion is irreversible and blocked by linked deals, and does nothing when declined', async () => {
    const requests = mockApi({
      'GET /api/v1/customers': { body: { items: [CUSTOMER], offset: 0, limit: 20 } },
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderApp(<CustomersPage />, '/customers')

    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('복구할 수 없'))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('연결된 Deal이 있으면 삭제할 수 없습니다'))
    expect(requests.some((r) => r.method === 'DELETE')).toBe(false)
  })

  it('shows the server message when a customer is referenced by deals', async () => {
    mockApi({
      'GET /api/v1/customers': { body: { items: [CUSTOMER], offset: 0, limit: 20 } },
      'DELETE /api/v1/customers/c-1': problem(409, 'invalid-state', '이 고객을 참조하는 Deal이 있어 삭제할 수 없습니다: c-1'),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<CustomersPage />, '/customers')

    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이 고객을 참조하는 Deal이 있어')
    expect(screen.getByText('네오인')).toBeInTheDocument()
  })

  it('sends empty optional fields as null when creating', async () => {
    const requests = mockApi({
      'GET /api/v1/customers': { body: { items: [], offset: 0, limit: 20 } },
      'POST /api/v1/customers': { status: 201, body: CUSTOMER },
    })
    renderApp(<CustomersPage />, '/customers')

    await userEvent.click(await screen.findByRole('button', { name: '고객 등록' }))
    await userEvent.type(screen.getByLabelText('회사명'), '네오인')
    await userEvent.type(screen.getByLabelText('담당자명'), '김철수')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await vi.waitFor(() => expect(requests.some((r) => r.method === 'POST')).toBe(true))
    expect(requests.find((r) => r.method === 'POST')?.body).toMatchObject({
      company_name: '네오인',
      contact_name: '김철수',
      email: null,
      phone: null,
      employee_count: null,
    })
  })
})
