import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { userRef } from '../../test/authFixtures'
import { mockApi, renderApp, type RecordedRequest } from '../../test/utils'
import { DealsPage } from './DealsPage'
import { useDealPipeline, useDeals } from './hooks'

const STAGE_CODES = [
  'prospecting',
  'introduction',
  'poc_preparation',
  'poc_completed',
  'technical_evaluation',
  'price_negotiation',
  'contract_completed',
  'lost',
]
const CUSTOMER = { id: 'c-1', company_name: '네오인' }
const deal = (n: number) => ({
  id: `d-${n}`,
  code: `DEAL-${String(n).padStart(3, '0')}`,
  name: 'ERP 구축',
  owner: userRef('u-3', '박영업'),
  vendor: 'SAP',
  solution: 'S/4',
  revenue_amount: '1',
  revenue_currency: 'KRW',
  revenue_date: '2026-06-30',
  customer_id: 'c-1',
  partner_id: null,
  stage: 'prospecting',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})
const ALL_DEALS_FULL_PAGE = Array.from({ length: 20 }, (_, n) => deal(n + 1))
const MINE_DEAL = deal(90)
const options = (items: unknown[]) => ({ body: { items, offset: 0, limit: 200 } })

/** 전체 5건 / 내 딜 1건으로 구분되는 파이프라인 응답. */
function pipelineReply(r: RecordedRequest) {
  const count = r.query.get('mine') === 'true' ? 1 : 5
  return {
    body: {
      stages: STAGE_CODES.map((stage) => ({
        stage,
        deal_count: stage === 'prospecting' ? count : 0,
        totals: [],
      })),
    },
  }
}

/** mine=true면 내 딜 1건, 아니면 전체(첫 쪽 20건, 다음 쪽 1건). */
function routes(overrides: Record<string, unknown> = {}) {
  return {
    'GET /api/v1/deals': (r: RecordedRequest) => ({
      body: {
        items:
          r.query.get('mine') === 'true'
            ? [MINE_DEAL]
            : r.query.get('offset') === '0'
              ? ALL_DEALS_FULL_PAGE
              : [deal(21)],
        offset: 0,
        limit: 20,
      },
    }),
    'GET /api/v1/deals/pipeline': pipelineReply,
    'GET /api/v1/customers': options([CUSTOMER]),
    'GET /api/v1/partners': options([]),
    ...overrides,
  }
}

const dealRequests = (requests: RecordedRequest[]) =>
  requests.filter((r) => r.method === 'GET' && r.path === '/api/v1/deals')
const pipelineRequests = (requests: RecordedRequest[]) =>
  requests.filter((r) => r.method === 'GET' && r.path === '/api/v1/deals/pipeline')

const prospectingCount = () => {
  const summary = screen.getByRole('region', { name: '파이프라인 현황' })
  return within(summary).getByText('기회발굴').closest('li') as HTMLElement
}

describe('DealsPage my deals toggle', () => {
  it('has an off "내 딜만" checkbox and explains that it means deals I am the owner of', async () => {
    mockApi(routes())

    renderApp(<DealsPage />, '/deals')

    await screen.findByRole('link', { name: 'DEAL-001' })
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).not.toBeChecked()
    expect(screen.getByText(/내가 담당자인 딜/)).toBeInTheDocument()
    expect(screen.queryByText(/내가 등록한 딜/)).not.toBeInTheDocument()
  })

  it('does not send mine in the initial requests', async () => {
    const requests = mockApi(routes())

    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await waitFor(() => expect(pipelineRequests(requests).length).toBeGreaterThan(0))

    expect(dealRequests(requests)[0]!.query.has('mine')).toBe(false)
    expect(pipelineRequests(requests)[0]!.query.has('mine')).toBe(false)
  })

  it('shows only my deals and my pipeline when the toggle is on', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await waitFor(() => expect(prospectingCount()).toHaveTextContent('5건'))

    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))

    expect(await screen.findByRole('link', { name: 'DEAL-090' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'DEAL-001' })).not.toBeInTheDocument()
    await waitFor(() => expect(prospectingCount()).toHaveTextContent('1건'))
    expect(dealRequests(requests).at(-1)!.query.get('mine')).toBe('true')
    expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('0')
    expect(pipelineRequests(requests).at(-1)!.query.get('mine')).toBe('true')
  })

  it('goes back to the first page when the toggle is turned on from a later page', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.click(screen.getByRole('button', { name: '다음' }))
    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('20'))

    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))

    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('mine')).toBe('true'))
    expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('0')
  })

  it('turning it off removes mine and shows everyone again, list and pipeline', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    await screen.findByRole('link', { name: 'DEAL-090' })

    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))

    expect(await screen.findByRole('link', { name: 'DEAL-001' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'DEAL-090' })).not.toBeInTheDocument()
    await waitFor(() => expect(prospectingCount()).toHaveTextContent('5건'))
    expect(dealRequests(requests).at(-1)!.query.has('mine')).toBe(false)
    expect(pipelineRequests(requests).at(-1)!.query.has('mine')).toBe(false)
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).not.toBeChecked()
  })

  it('keeps the entered search conditions together with mine', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.type(screen.getByLabelText('검색어'), 'erp')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))
    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('keyword')).toBe('erp'))

    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))

    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('mine')).toBe('true'))
    const query = dealRequests(requests).at(-1)!.query
    expect(query.get('keyword')).toBe('erp')
    expect(query.get('offset')).toBe('0')
  })

  it('keeps mine when a search is submitted afterwards', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    await screen.findByRole('link', { name: 'DEAL-090' })

    await screen.findByRole('option', { name: '박영업' })
    await userEvent.selectOptions(screen.getByLabelText('Owner'), 'u-3')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('owner_user_id')).toBe('u-3'))
    expect(dealRequests(requests).at(-1)!.query.get('mine')).toBe('true')
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).toBeChecked()
  })

  it('tells that nothing matches when I have no deals', async () => {
    mockApi(
      routes({
        'GET /api/v1/deals': (r: RecordedRequest) => ({
          body: { items: r.query.get('mine') === 'true' ? [] : [deal(1)], offset: 0, limit: 20 },
        }),
      }),
    )
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))

    expect(await screen.findByText('조건에 맞는 딜이 없습니다.')).toBeInTheDocument()
    expect(screen.queryByText('등록된 딜이 없습니다.')).not.toBeInTheDocument()
  })
})

describe('DealsPage search with mine on', () => {
  it('refetches the list when searching with an empty form while mine is on', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    await screen.findByRole('link', { name: 'DEAL-090' })
    const mineCalls = () =>
      dealRequests(requests).filter((r) => r.query.get('mine') === 'true').length
    await waitFor(() => expect(mineCalls()).toBe(1))

    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(mineCalls()).toBe(2))
    expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('0')
    expect(screen.getByRole('checkbox', { name: '내 딜만' })).toBeChecked()
  })

  it('refetches when the same conditions are searched again while mine is on', async () => {
    const requests = mockApi(routes())
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await userEvent.click(screen.getByRole('checkbox', { name: '내 딜만' }))
    await screen.findByRole('link', { name: 'DEAL-090' })
    await userEvent.type(screen.getByLabelText('검색어'), 'erp')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))
    const sameCalls = () =>
      dealRequests(requests).filter(
        (r) => r.query.get('mine') === 'true' && r.query.get('keyword') === 'erp',
      ).length
    await waitFor(() => expect(sameCalls()).toBe(1))

    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(sameCalls()).toBe(2))
  })
})

describe('mine in the deal hooks', () => {
  function wrapper({ children }: { children: ReactNode }) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }

  it('useDeals sends mine=true and drops mine=false', async () => {
    const requests = mockApi(routes())

    const { result: on } = renderHook(() => useDeals({ mine: true }, 0), { wrapper })
    await waitFor(() => expect(on.current.isSuccess).toBe(true))
    const { result: off } = renderHook(() => useDeals({ mine: false }, 0), { wrapper })
    await waitFor(() => expect(off.current.isSuccess).toBe(true))

    expect(dealRequests(requests)[0]!.query.get('mine')).toBe('true')
    expect(dealRequests(requests)[1]!.query.has('mine')).toBe(false)
  })

  it('useDealPipeline sends mine=true only when asked', async () => {
    const requests = mockApi(routes())

    const { result: on } = renderHook(() => useDealPipeline({ mine: true }), { wrapper })
    await waitFor(() => expect(on.current.isSuccess).toBe(true))
    const { result: plain } = renderHook(() => useDealPipeline(), { wrapper })
    await waitFor(() => expect(plain.current.isSuccess).toBe(true))

    expect(pipelineRequests(requests)[0]!.query.get('mine')).toBe('true')
    expect(pipelineRequests(requests)[1]!.query.has('mine')).toBe(false)
  })

  it('useDealPipeline keeps mine and everyone as separate cache entries', async () => {
    const requests = mockApi(routes())

    const { result, rerender } = renderHook(({ mine }) => useDealPipeline({ mine }), {
      wrapper,
      initialProps: { mine: false },
    })
    await waitFor(() => expect(result.current.data?.stages[0]!.deal_count).toBe(5))
    rerender({ mine: true })

    await waitFor(() => expect(result.current.data?.stages[0]!.deal_count).toBe(1))
    expect(pipelineRequests(requests).length).toBe(2)
  })
})
