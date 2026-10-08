import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, type RecordedRequest } from '../../test/utils'
import { DealsPage } from './DealsPage'
import { useDeals } from './hooks'

const CUSTOMER = { id: 'c-1', company_name: '네오인' }
const PARTNER = { id: 'p-1', company_name: '한빛' }
const deal = (n: number) => ({
  id: `d-${n}`,
  code: `DEAL-${String(n).padStart(3, '0')}`,
  name: 'ERP 구축',
  owner: '박영업',
  vendor: 'SAP',
  solution: 'S/4',
  revenue_amount: '1',
  revenue_currency: 'KRW',
  revenue_date: '2026-06-30',
  customer_id: 'c-1',
  partner_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})
const FULL_PAGE = Array.from({ length: 20 }, (_, n) => deal(n + 1))
const options = (items: unknown[]) => ({ body: { items, offset: 0, limit: 200 } })
const dealRequests = (requests: RecordedRequest[]) =>
  requests.filter((r) => r.method === 'GET' && r.path === '/api/v1/deals')

function routes() {
  return {
    'GET /api/v1/deals': (r: RecordedRequest) => ({
      body: { items: r.query.get('offset') === '0' ? FULL_PAGE : [deal(21)], offset: 0, limit: 20 },
    }),
    'GET /api/v1/customers': options([CUSTOMER]),
    'GET /api/v1/partners': options([PARTNER]),
  }
}

describe('DealsPage search', () => {
  it('requests only offset and limit when opened without conditions', async () => {
    const requests = mockApi(routes())

    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    const first = dealRequests(requests)[0]!
    expect([...first.query.keys()].sort()).toEqual(['limit', 'offset'])
    expect(first.query.get('offset')).toBe('0')
    expect(first.query.get('limit')).toBe('20')
  })

  it('searches with the entered conditions, the end date as the next day', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await screen.findByRole('option', { name: '한빛' })

    await userEvent.type(screen.getByLabelText('검색어'), 'erp')
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')
    await userEvent.type(screen.getByLabelText('매출 종료일'), '2026-06-30')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(dealRequests(requests).length).toBeGreaterThan(1))
    const query = dealRequests(requests).at(-1)!.query
    expect(query.get('keyword')).toBe('erp')
    expect(query.get('customer_id')).toBe('c-1')
    expect(query.get('revenue_to')).toBe('2026-07-01')
    expect(query.get('offset')).toBe('0')
    expect(query.has('owner')).toBe(false)
    expect(query.has('vendor')).toBe(false)
    expect(query.has('partner_id')).toBe(false)
    expect(query.has('revenue_from')).toBe(false)
  })

  it('goes back to the first page when searching from a later page', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.click(screen.getByRole('button', { name: '다음' }))
    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('20'))

    await userEvent.type(screen.getByLabelText('Owner'), '박영업')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('owner')).toBe('박영업'))
    expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('0')
  })

  it('tells that nothing matches when a search returns no deals', async () => {
    mockApi({
      ...routes(),
      'GET /api/v1/deals': (r: RecordedRequest) => ({
        body: { items: r.query.has('keyword') ? [] : [deal(1)], offset: 0, limit: 20 },
      }),
    })
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    await userEvent.type(screen.getByLabelText('검색어'), 'zzz')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('조건에 맞는 딜이 없습니다.')).toBeInTheDocument()
  })

  it('keeps the plain empty message when no condition is set', async () => {
    mockApi({ ...routes(), 'GET /api/v1/deals': { body: { items: [], offset: 0, limit: 20 } } })

    renderApp(<DealsPage />, '/deals')

    expect(await screen.findByText('등록된 딜이 없습니다.')).toBeInTheDocument()
  })

  it('keeps the plain empty message when searching with an empty form', async () => {
    let calls = 0
    mockApi({
      ...routes(),
      'GET /api/v1/deals': () => ({
        body: { items: calls++ === 0 ? [deal(1)] : [], offset: 0, limit: 20 },
      }),
    })
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('등록된 딜이 없습니다.')).toBeInTheDocument()
    expect(screen.queryByText('조건에 맞는 딜이 없습니다.')).not.toBeInTheDocument()
  })
})

describe('useDeals', () => {
  function wrapper({ children }: { children: ReactNode }) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }

  it('drops empty values and sends the filters with the offset', async () => {
    const requests = mockApi(routes())

    const { result } = renderHook(
      () => useDeals({ keyword: 'erp', owner: '', vendor: undefined, revenue_from: '2026-06-01' }, 20),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const query = dealRequests(requests)[0]!.query
    expect(query.get('keyword')).toBe('erp')
    expect(query.get('revenue_from')).toBe('2026-06-01')
    expect(query.get('offset')).toBe('20')
    expect(query.get('limit')).toBe('20')
    expect(query.has('owner')).toBe(false)
    expect(query.has('vendor')).toBe(false)
  })

  it('refetches when a filter changes', async () => {
    const requests = mockApi(routes())

    const { result, rerender } = renderHook(({ keyword }) => useDeals({ keyword }, 0), {
      wrapper,
      initialProps: { keyword: 'a' },
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    rerender({ keyword: 'b' })

    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('keyword')).toBe('b'))
    expect(dealRequests(requests).length).toBe(2)
  })
})
