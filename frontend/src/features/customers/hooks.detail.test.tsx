import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { DETAIL_CUSTOMER, DETAIL_PARTNER } from '../../test/dealFixtures'
import { mockApi, problem } from '../../test/utils'
import { usePartner } from '../partners/hooks'
import { useCustomer } from './hooks'

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('single customer and partner hooks', () => {
  it('useCustomer loads one customer by id', async () => {
    const requests = mockApi({ 'GET /api/v1/customers/c-1': { body: DETAIL_CUSTOMER } })

    const { result } = renderHook(() => useCustomer('c-1'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.company_name).toBe('네오인')
    expect(requests[0]!.path).toBe('/api/v1/customers/c-1')
  })

  it('useCustomer exposes a 404 as an error', async () => {
    mockApi({ 'GET /api/v1/customers/c-1': problem(404, 'not-found', '고객을 찾을 수 없습니다') })

    const { result } = renderHook(() => useCustomer('c-1'), { wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('usePartner loads one partner by id', async () => {
    const requests = mockApi({ 'GET /api/v1/partners/p-1': { body: DETAIL_PARTNER } })

    const { result } = renderHook(() => usePartner('p-1'), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.company_name).toBe('한빛')
    expect(requests[0]!.path).toBe('/api/v1/partners/p-1')
  })

  it('usePartner sends no request for an empty id', async () => {
    const requests = mockApi({})

    renderHook(() => usePartner(''), { wrapper })
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(requests).toHaveLength(0)
  })
})
