import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { DIRECTORY_SETTINGS, ME_ADMIN } from '../../test/authFixtures'
import { mockApi, problem } from '../../test/utils'
import { useSaveDirectory, useTestDirectory } from '../settings/hooks'
import { useLogin, useSetupAdmin } from './hooks'

const DIRECTORY_BODY = {
  server_urls: ['ldaps://dc1.corp.test'],
  use_starttls: false,
  ca_cert_pem: null,
  bind_template: 'CORP\\{login_id}',
  base_dn: 'dc=corp,dc=test',
  user_filter: '(&(objectClass=user)(sAMAccountName={login_id}))',
  display_name_attribute: 'displayName',
  email_attribute: 'mail',
  connect_timeout_seconds: 5,
  receive_timeout_seconds: 10,
  password: 'bind-secret',
}

/** 화면이 사라진 뒤에도 비밀번호가 든 mutation(variables)이 캐시에 남으면 안 된다. */
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
  return { client, wrapper }
}

const cached = (client: QueryClient) => client.getMutationCache().getAll()

describe('mutations that carry passwords', () => {
  const cases = [
    ['login', useLogin, { 'POST /api/v1/auth/login': { body: ME_ADMIN } }, { login_id: 'kim', password: 'pw-secret' }],
    ['setup admin', useSetupAdmin, { 'POST /api/v1/auth/setup': { body: ME_ADMIN } }, { login_id: 'root', password: 'pw-secret' }],
    [
      'save directory',
      useSaveDirectory,
      { 'PUT /api/v1/settings/directory': { body: DIRECTORY_SETTINGS } },
      { ...DIRECTORY_BODY, expected_revision: 1 },
    ],
    ['test directory', useTestDirectory, { 'POST /api/v1/settings/directory/test': { body: { ok: true } } }, DIRECTORY_BODY],
  ] as const

  it.each(cases)('drops the %s variables from the cache once the screen is gone (success)', async (_name, hook, routes, body) => {
    mockApi(routes as never)
    const { client, wrapper } = setup()
    const { result, unmount } = renderHook(() => (hook as () => { mutateAsync: (b: unknown) => Promise<unknown> })(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync(body).catch(() => undefined)
    })
    unmount()
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

    expect(cached(client)).toHaveLength(0)
  })

  it('drops the login variables from the cache after a failed attempt too', async () => {
    mockApi({ 'POST /api/v1/auth/login': problem(401, 'unauthenticated', 'x') })
    const { client, wrapper } = setup()
    const { result, unmount } = renderHook(() => useLogin(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ login_id: 'kim', password: 'wrong' }).catch(() => undefined)
    })
    unmount()
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 20))
    })

    expect(cached(client)).toHaveLength(0)
  })
})
