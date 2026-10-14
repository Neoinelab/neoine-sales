import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ME_SALES, userRef } from '../../test/authFixtures'
import { mockApi, renderApp } from '../../test/utils'
import { DealForm } from './DealForm'
import type { Deal } from './hooks'

const page = (items: unknown[]) => ({ body: { items, offset: 0, limit: 200 } })
const LOST_DEAL = {
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
  stage: 'lost',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
} as Deal

describe('DealForm and stages', () => {
  it('does not send stage when editing a deal', async () => {
    const requests = mockApi({
      'GET /api/v1/customers': page([{ id: 'c-1', company_name: '네오인' }]),
      'GET /api/v1/partners': page([]),
      'PUT /api/v1/deals/d-1': { body: LOST_DEAL },
    })
    const done = vi.fn()
    renderApp(<DealForm initial={LOST_DEAL} onDone={done} />)
    await screen.findByRole('option', { name: '네오인' })

    await userEvent.clear(screen.getByLabelText('Deal Name'))
    await userEvent.type(screen.getByLabelText('Deal Name'), '이름만 변경')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(done).toHaveBeenCalled())
    const put = requests.find((r) => r.method === 'PUT')
    expect(put?.body).toMatchObject({ name: '이름만 변경', code: 'DEAL-001' })
    expect(Object.keys(put?.body as object)).not.toContain('stage')
  })

  it('has no stage input, because stages change only through the stage action', async () => {
    mockApi({ 'GET /api/v1/customers': page([]), 'GET /api/v1/partners': page([]) })

    renderApp(<DealForm onDone={() => undefined} />)

    expect(screen.queryByLabelText('단계')).not.toBeInTheDocument()
  })

  it('does not send stage when registering a new deal', async () => {
    const requests = mockApi({
      'GET /api/v1/customers': page([{ id: 'c-1', company_name: '네오인' }]),
      'GET /api/v1/partners': page([]),
      'POST /api/v1/deals': { status: 201, body: LOST_DEAL },
    })
    const done = vi.fn()
    renderApp(<DealForm onDone={done} />)
    await screen.findByRole('option', { name: '네오인' })
    for (const [label, value] of [['Deal Code', 'a'], ['Deal Name', 'b'], ['Vendor', 'd'], ['Solution', 'e'], ['매출금액', '1'], ['매출일', '2026-06-30']] as const) {
      await userEvent.type(screen.getByLabelText(label), value)
    }
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(done).toHaveBeenCalled())
    const post = requests.find((r) => r.method === 'POST')
    expect(Object.keys(post?.body as object)).not.toContain('stage')
  })
})

describe('DealForm owner selection', () => {
  const routes = {
    'GET /api/v1/customers': page([{ id: 'c-1', company_name: '네오인' }]),
    'GET /api/v1/partners': page([]),
  }

  it('preselects the signed-in user as the owner of a new deal and sends owner_user_id', async () => {
    const requests = mockApi({ ...routes, 'POST /api/v1/deals': { status: 201, body: LOST_DEAL } })
    const done = vi.fn()
    renderApp(<DealForm onDone={done} />)
    await screen.findByRole('option', { name: '네오인' })
    await waitFor(() => expect(screen.getByLabelText('Deal Owner')).toHaveValue(ME_SALES.user_id))
    for (const [label, value] of [['Deal Code', 'a'], ['Deal Name', 'b'], ['Vendor', 'd'], ['Solution', 'e'], ['매출금액', '1'], ['매출일', '2026-06-30']] as const) {
      await userEvent.type(screen.getByLabelText(label), value)
    }
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(done).toHaveBeenCalled())
    const body = requests.find((r) => r.method === 'POST')?.body as Record<string, unknown>
    expect(body.owner_user_id).toBe(ME_SALES.user_id)
    expect(body).not.toHaveProperty('owner')
  })

  it('sends the user picked from the list as owner_user_id', async () => {
    const requests = mockApi({ ...routes, 'POST /api/v1/deals': { status: 201, body: LOST_DEAL } })
    renderApp(<DealForm onDone={() => undefined} />)
    await screen.findByRole('option', { name: '네오인' })
    await userEvent.selectOptions(screen.getByLabelText('Deal Owner'), 'u-3')
    for (const [label, value] of [['Deal Code', 'a'], ['Deal Name', 'b'], ['Vendor', 'd'], ['Solution', 'e'], ['매출금액', '1'], ['매출일', '2026-06-30']] as const) {
      await userEvent.type(screen.getByLabelText(label), value)
    }
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')

    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(requests.some((r) => r.method === 'POST')).toBe(true))
    expect((requests.find((r) => r.method === 'POST')?.body as Record<string, unknown>).owner_user_id).toBe('u-3')
  })

  it('keeps the existing owner on edit, even when the owner has resigned', async () => {
    const resigned = { ...LOST_DEAL, owner: userRef('u-7', '이퇴사', true) } as Deal
    const requests = mockApi({ ...routes, 'PUT /api/v1/deals/d-1': { body: resigned } })
    renderApp(<DealForm initial={resigned} onDone={() => undefined} />)
    await screen.findByRole('option', { name: '네오인' })

    expect(await screen.findByRole('option', { name: '이퇴사(퇴사)' })).toBeDisabled()
    expect(screen.getByLabelText('Deal Owner')).toHaveValue('u-7')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(requests.some((r) => r.method === 'PUT')).toBe(true))
    expect((requests.find((r) => r.method === 'PUT')?.body as Record<string, unknown>).owner_user_id).toBe('u-7')
  })
})
