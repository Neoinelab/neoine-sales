import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../../test/utils'
import { useDealPipeline, useDealStageChanges, useDeals } from './hooks'

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('deal stage hooks', () => {
  it('useDeals sends the stage filter and drops an empty one', async () => {
    const requests = mockApi({ 'GET /api/v1/deals': { body: { items: [], offset: 0, limit: 20 } } })

    const { result: withStage } = renderHook(() => useDeals({ stage: 'lost' }, 0), { wrapper })
    await waitFor(() => expect(withStage.current.isSuccess).toBe(true))
    const { result: without } = renderHook(() => useDeals({ keyword: '' }, 0), { wrapper })
    await waitFor(() => expect(without.current.isSuccess).toBe(true))

    expect(requests[0]!.query.get('stage')).toBe('lost')
    expect(requests[1]!.query.has('stage')).toBe(false)
  })

  it('useDealPipeline loads the pipeline from the pipeline endpoint', async () => {
    const stages = [{ stage: 'prospecting', deal_count: 2, totals: [{ currency: 'KRW', amount: '10' }] }]
    const requests = mockApi({ 'GET /api/v1/deals/pipeline': { body: { stages } } })

    const { result } = renderHook(() => useDealPipeline(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.stages).toEqual(stages)
    expect(requests[0]!.path).toBe('/api/v1/deals/pipeline')
  })

  it('useDealStageChanges loads the history of one deal page by page', async () => {
    const change = {
      id: 'h-1',
      deal_id: 'd-1',
      from_stage: 'prospecting',
      to_stage: 'lost',
      reason: '예산 부족',
      changed_by: { id: 'u-2', name: '개발 사용자(sales)', resigned: false, label: '개발 사용자(sales)' },
      changed_at: '2026-01-01T00:00:00Z',
    }
    const requests = mockApi({
      'GET /api/v1/deals/d-1/stage-changes': { body: { items: [change], offset: 20, limit: 20 } },
    })

    const { result } = renderHook(() => useDealStageChanges('d-1', 20), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.items).toEqual([change])
    expect(requests[0]!.query.get('offset')).toBe('20')
  })
})
