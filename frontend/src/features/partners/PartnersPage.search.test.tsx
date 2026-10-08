import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, type RecordedRequest } from '../../test/utils'
import { usePartners } from './hooks'
import { PartnersPage } from './PartnersPage'

const BASE = '/api/v1/partners'
const item = (n: number) => ({
  id: `x-${n}`,
  company_name: `회사${n}`,
  contact_name: `담당${n}`,
  contact_title: '팀장',
  email: `x${n}@sample.example`,
  phone: '010-1234-5678',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})
const FULL_PAGE = Array.from({ length: 20 }, (_, n) => item(n + 1))
const listRequests = (requests: RecordedRequest[]) =>
  requests.filter((r) => r.method === 'GET' && r.path === BASE)

describe('PartnersPage search', () => {
  it('requests only offset and limit when opened without a keyword', async () => {
    const requests = mockApi({ [`GET ${BASE}`]: { body: { items: [item(1)], offset: 0, limit: 20 } } })

    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('회사1')

    const first = listRequests(requests)[0]!
    expect([...first.query.keys()].sort()).toEqual(['limit', 'offset'])
    expect(first.query.get('offset')).toBe('0')
    expect(first.query.get('limit')).toBe('20')
  })

  it('renders a search form with a keyword field and a search button', async () => {
    mockApi({ [`GET ${BASE}`]: { body: { items: [item(1)], offset: 0, limit: 20 } } })

    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('회사1')

    expect(screen.getByRole('search')).toBeInTheDocument()
    expect(screen.getByLabelText('검색어')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument()
  })

  it('searches 파트너 by keyword from the first page', async () => {
    const requests = mockApi({
      [`GET ${BASE}`]: (r: RecordedRequest) => ({
        body: { items: r.query.get('offset') === '0' ? FULL_PAGE : [item(21)], offset: 0, limit: 20 },
      }),
    })
    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('회사1')
    await userEvent.click(screen.getByRole('button', { name: '다음' }))
    await waitFor(() => expect(listRequests(requests).at(-1)!.query.get('offset')).toBe('20'))

    await userEvent.type(screen.getByLabelText('검색어'), '회사')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(listRequests(requests).at(-1)!.query.get('keyword')).toBe('회사'))
    const query = listRequests(requests).at(-1)!.query
    expect(query.get('offset')).toBe('0')
    expect(query.get('limit')).toBe('20')
  })

  it('searches when pressing Enter in the keyword field', async () => {
    const requests = mockApi({ [`GET ${BASE}`]: { body: { items: [item(1)], offset: 0, limit: 20 } } })
    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('회사1')

    await userEvent.type(screen.getByLabelText('검색어'), 'abc{Enter}')

    await waitFor(() => expect(listRequests(requests).at(-1)!.query.get('keyword')).toBe('abc'))
  })

  it('shows an empty search message when nothing matches', async () => {
    mockApi({
      [`GET ${BASE}`]: (r: RecordedRequest) => ({
        body: { items: r.query.has('keyword') ? [] : [item(1)], offset: 0, limit: 20 },
      }),
    })
    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('회사1')

    await userEvent.type(screen.getByLabelText('검색어'), 'zzz')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('조건에 맞는 파트너가 없습니다.')).toBeInTheDocument()
    expect(screen.queryByText('등록된 파트너가 없습니다.')).not.toBeInTheDocument()
  })

  it('keeps the plain empty message when no keyword is set', async () => {
    mockApi({ [`GET ${BASE}`]: { body: { items: [], offset: 0, limit: 20 } } })

    renderApp(<PartnersPage />, '/partners')

    expect(await screen.findByText('등록된 파트너가 없습니다.')).toBeInTheDocument()
  })

  it('keeps the plain empty message when searching with an empty form', async () => {
    let calls = 0
    mockApi({
      [`GET ${BASE}`]: () => ({ body: { items: calls++ === 0 ? [item(1)] : [], offset: 0, limit: 20 } }),
    })
    renderApp(<PartnersPage />, '/partners')
    await screen.findByText('회사1')

    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('등록된 파트너가 없습니다.')).toBeInTheDocument()
    expect(screen.queryByText('조건에 맞는 파트너가 없습니다.')).not.toBeInTheDocument()
  })
})

describe('usePartners', () => {
  function wrapper({ children }: { children: ReactNode }) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }

  it('sends the keyword with the offset and the page size', async () => {
    const requests = mockApi({ [`GET ${BASE}`]: { body: { items: [], offset: 0, limit: 20 } } })

    const { result } = renderHook(() => usePartners({ keyword: '회사' }, 20), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const query = listRequests(requests)[0]!.query
    expect(query.get('keyword')).toBe('회사')
    expect(query.get('offset')).toBe('20')
    expect(query.get('limit')).toBe('20')
  })

  it('drops an empty keyword', async () => {
    const requests = mockApi({ [`GET ${BASE}`]: { body: { items: [], offset: 0, limit: 20 } } })

    const { result } = renderHook(() => usePartners({ keyword: '' }, 0), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listRequests(requests)[0]!.query.has('keyword')).toBe(false)
  })

  it('refetches when the keyword changes', async () => {
    const requests = mockApi({ [`GET ${BASE}`]: { body: { items: [], offset: 0, limit: 20 } } })

    const { result, rerender } = renderHook(({ keyword }) => usePartners({ keyword }, 0), {
      wrapper,
      initialProps: { keyword: 'a' },
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    rerender({ keyword: 'b' })

    await waitFor(() => expect(listRequests(requests).at(-1)!.query.get('keyword')).toBe('b'))
    expect(listRequests(requests).length).toBe(2)
  })
})
