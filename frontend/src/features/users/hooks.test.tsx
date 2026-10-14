import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { USER_ROWS } from '../../test/authFixtures'
import { mockApi } from '../../test/utils'
import { useAddUser, useDeleteUser } from './hooks'

afterEach(() => vi.restoreAllMocks())

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  client.setQueryData(['user-options', { include_resigned: false }], { items: [], offset: 0, limit: 200 })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

const optionsInvalidated = (client: QueryClient) =>
  client.getQueryCache().findAll({ queryKey: ['user-options'] }).every((q) => q.state.isInvalidated)

describe('user mutations refresh the user-options candidates', () => {
  it('invalidates user-options after adding a user', async () => {
    mockApi({ 'POST /api/v1/users': { status: 201, body: USER_ROWS[0] }, 'GET /api/v1/users': { body: { items: [], offset: 0, limit: 50 } } })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useAddUser(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ login_id: 'lee', role: 'user' })
    })

    expect(optionsInvalidated(client)).toBe(true)
  })

  it('invalidates user-options after deleting a user', async () => {
    mockApi({
      'DELETE /api/v1/users/u-3': { body: { outcome: 'resigned' } },
      'GET /api/v1/users': { body: { items: [], offset: 0, limit: 50 } },
    })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useDeleteUser(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync('u-3')
    })

    expect(optionsInvalidated(client)).toBe(true)
  })
})
