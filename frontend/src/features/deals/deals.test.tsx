import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { userRef } from '../../test/authFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { DealForm } from './DealForm'
import { DealsPage } from './DealsPage'

const CUSTOMER = { id: 'c-1', company_name: '네오인' }
const PARTNER = { id: 'p-1', company_name: '한빛' }
const page = (items: unknown[]) => ({ body: { items, offset: 0, limit: 200 } })
const DEAL = {
  id: 'd-1',
  code: 'DEAL-001',
  name: 'ERP 구축',
  owner: userRef('u-3', '박영업'),
  vendor: 'SAP',
  solution: 'S/4',
  revenue_amount: '150000000',
  revenue_currency: 'KRW',
  revenue_date: '2026-06-30',
  customer_id: 'c-1',
  partner_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('DealForm', () => {
  it('sends the amount as text and an empty partner as null', async () => {
    const requests = mockApi({
      'GET /api/v1/customers': page([CUSTOMER]),
      'GET /api/v1/partners': page([PARTNER]),
      'POST /api/v1/deals': { status: 201, body: DEAL },
    })
    const done = vi.fn()
    renderApp(<DealForm onDone={done} />)
    await screen.findByRole('option', { name: '네오인' })

    await userEvent.type(screen.getByLabelText('Deal Code'), 'deal-001')
    await userEvent.type(screen.getByLabelText('Deal Name'), 'ERP 구축')
    await userEvent.selectOptions(screen.getByLabelText('Deal Owner'), 'u-3')
    await userEvent.type(screen.getByLabelText('Vendor'), 'SAP')
    await userEvent.type(screen.getByLabelText('Solution'), 'S/4')
    await userEvent.type(screen.getByLabelText('매출금액'), '1234567.8912')
    await userEvent.type(screen.getByLabelText('매출일'), '2026-06-30')
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(done).toHaveBeenCalled())
    const post = requests.find((r) => r.method === 'POST')
    expect(post?.body).toMatchObject({
      code: 'deal-001',
      revenue_amount: '1234567.8912',
      revenue_currency: 'KRW',
      customer_id: 'c-1',
      partner_id: null,
      owner_user_id: 'u-3',
    })
  })

  it('shows the server message and stays open when saving fails', async () => {
    mockApi({
      'GET /api/v1/customers': page([CUSTOMER]),
      'GET /api/v1/partners': page([]),
      'POST /api/v1/deals': problem(409, 'already-exists', '이미 존재하는 Deal Code입니다: DEAL-001'),
    })
    const done = vi.fn()
    renderApp(<DealForm onDone={done} />)
    await screen.findByRole('option', { name: '네오인' })
    for (const [label, value] of [['Deal Code', 'a'], ['Deal Name', 'b'],['Vendor', 'd'], ['Solution', 'e'], ['매출금액', '1'], ['매출일', '2026-06-30']] as const) {
      await userEvent.type(screen.getByLabelText(label), value)
    }
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 존재하는 Deal Code')
    expect(done).not.toHaveBeenCalled()
  })
})

describe('DealsPage', () => {
  it('lists deals with the customer name and formatted amount', async () => {
    mockApi({
      'GET /api/v1/deals': page([DEAL]),
      'GET /api/v1/customers': page([CUSTOMER]),
    })

    renderApp(<DealsPage />, '/deals')

    const row = (await screen.findByRole('link', { name: 'DEAL-001' })).closest('tr') as HTMLElement
    expect(within(row).getByText('150,000,000 KRW')).toBeInTheDocument()
    expect(within(row).getByText('네오인')).toBeInTheDocument()
    expect(within(row).getByText('박영업')).toBeInTheDocument()
  })

  it('shows a resigned owner by the server label', async () => {
    mockApi({
      'GET /api/v1/deals': page([{ ...DEAL, owner: userRef('u-7', '이퇴사', true) }]),
      'GET /api/v1/customers': page([CUSTOMER]),
    })

    renderApp(<DealsPage />, '/deals')

    const row = (await screen.findByRole('link', { name: 'DEAL-001' })).closest('tr') as HTMLElement
    expect(within(row).getByText('이퇴사(퇴사)')).toBeInTheDocument()
  })

  it('asks for confirmation before deleting', async () => {
    const requests = mockApi({
      'GET /api/v1/deals': page([DEAL]),
      'GET /api/v1/customers': page([CUSTOMER]),
      'DELETE /api/v1/deals/d-1': { status: 204 },
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    renderApp(<DealsPage />, '/deals')
    const button = await screen.findByRole('button', { name: '삭제' })

    await userEvent.click(button)
    expect(requests.some((r) => r.method === 'DELETE')).toBe(false)
    await userEvent.click(button)

    await waitFor(() => expect(requests.some((r) => r.method === 'DELETE')).toBe(true))
    expect(confirm).toHaveBeenCalledTimes(2)
  })
})
