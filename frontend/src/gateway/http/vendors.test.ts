import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { createVendorsHttp } from './vendors'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const solution = (over: Record<string, unknown> = {}) => ({
  id: 1,
  vendor_id: 1,
  name: 'ITDR',
  usage_count: 0,
  created_at: '2026-10-01T09:00:00+09:00',
  updated_at: '2026-10-01T09:00:00+09:00',
  ...over,
})
const vendor = (over: Record<string, unknown> = {}) => ({
  id: 1,
  name: 'Silverfort',
  usage_count: 3,
  created_at: '2026-10-01T09:00:00+09:00',
  updated_at: '2026-10-01T09:00:00+09:00',
  solutions: [solution({ usage_count: 3 })],
  ...over,
})

describe('vendors over HTTP', () => {
  it('list reads GET /vendors and maps the nested solutions', async () => {
    const { calls } = stubFetch(json([vendor()]))

    const vendors = await createVendorsHttp().list()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/vendors' })
    expect(vendors).toEqual([
      { id: 1, name: 'Silverfort', usageCount: 3, solutions: [{ id: 1, vendorId: 1, name: 'ITDR', usageCount: 3 }] },
    ])
  })

  it('create posts the name', async () => {
    const { calls } = stubFetch(json(vendor({ solutions: [], usage_count: 0 }), 201, { Location: '/api/v1/vendors/1' }))

    const created = await createVendorsHttp().create('Silverfort')

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/vendors', body: { name: 'Silverfort' } })
    expect(created).toMatchObject({ id: 1, usageCount: 0, solutions: [] })
  })

  it('rename patches the name of the vendor', async () => {
    const { calls } = stubFetch(json(vendor({ name: 'New' })))

    const renamed = await createVendorsHttp().rename(1, 'New')

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/vendors/1', body: { name: 'New' } })
    expect(renamed.name).toBe('New')
  })

  it('remove deletes and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createVendorsHttp().remove(1)).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/vendors/1' })
  })

  it('createSolution posts under the vendor path', async () => {
    const { calls } = stubFetch(json(solution(), 201, { Location: '/api/v1/vendors/1/solutions/1' }))

    const created = await createVendorsHttp().createSolution(1, 'ITDR')

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/vendors/1/solutions', body: { name: 'ITDR' } })
    expect(created).toEqual({ id: 1, vendorId: 1, name: 'ITDR', usageCount: 0 })
  })

  it('renameSolution patches with both ids in the path', async () => {
    const { calls } = stubFetch(json(solution({ name: 'MFA' })))

    const renamed = await createVendorsHttp().renameSolution(1, 1, 'MFA')

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/vendors/1/solutions/1', body: { name: 'MFA' } })
    expect(renamed.name).toBe('MFA')
  })

  it('removeSolution deletes with both ids in the path', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createVendorsHttp().removeSolution(1, 1)).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/vendors/1/solutions/1' })
  })

  it.each([
    [409, 'already-exists', '이미 있는 Vendor 이름입니다.', 'conflict'],
    [409, 'invalid-state', '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)', 'conflict'],
    [422, 'invalid-value', 'Vendor 이름을 입력하세요.', 'validation'],
    [403, 'forbidden', '관리자 권한이 필요합니다', 'forbidden'],
  ])('failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createVendorsHttp().create('x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  it('the http gateway exposes vendors', () => {
    expect(createHttpGateway().vendors).toBeDefined()
  })
})
