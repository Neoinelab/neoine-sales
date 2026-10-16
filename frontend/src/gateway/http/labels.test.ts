import { afterEach, describe, expect, it, vi } from 'vitest'
import { createLabelsHttp } from './labels'
import { json, noContent, problem, stubFetch, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const label = (over: Record<string, unknown> = {}) => ({
  id: 'l1',
  category: 'budget',
  name: '단독 예산 확보',
  is_default: true,
  created_by: null,
  created_at: '2026-01-01T09:00:00+09:00',
  updated_at: '2026-01-01T09:00:00+09:00',
  usage_count: 0,
  ...over,
})

describe('labels over HTTP', () => {
  it('list reads GET /bant-labels and maps default and custom labels', async () => {
    const { calls } = stubFetch(json([label(), label({ id: 'l2', name: '내 라벨', is_default: false, created_by: userRefBody('u1', '김영업'), usage_count: 2 })]))

    const labels = await createLabelsHttp().list()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/bant-labels' })
    expect(labels[0]).toEqual({
      id: 'l1',
      category: 'budget',
      name: '단독 예산 확보',
      isDefault: true,
      createdBy: null,
      createdAt: '2026-01-01T09:00:00+09:00',
      usageCount: 0,
    })
    expect(labels[1]).toMatchObject({ isDefault: false, usageCount: 2, createdBy: { id: 'u1', name: '김영업' } })
  })

  it('create posts the category and the name', async () => {
    const { calls } = stubFetch(json(label({ id: 'l3', name: '신규', is_default: false }), 201))

    const created = await createLabelsHttp().create('need', '신규')

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/bant-labels', body: { category: 'need', name: '신규' } })
    expect(created).toMatchObject({ id: 'l3', name: '신규' })
  })

  it.each([
    [409, 'already-exists', '같은 구분에 이미 있는 Label 이름입니다.', 'conflict'],
    [422, 'invalid-value', 'Label 이름을 입력하세요.', 'validation'],
    [422, 'invalid-value', 'Label 이름은 50자 이내로 입력하세요.', 'validation'],
    [403, 'forbidden', '이 작업을 수행할 권한이 없습니다.', 'forbidden'],
  ])('create failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createLabelsHttp().create('budget', 'x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  it('rename patches the name', async () => {
    const { calls } = stubFetch(json(label({ name: '새 이름' })))

    await createLabelsHttp().rename('l1', '새 이름')

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/bant-labels/l1', body: { name: '새 이름' } })
  })

  it('remove deletes and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createLabelsHttp().remove('l1')).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/bant-labels/l1' })
  })

  it('remove maps the in-use refusal to a conflict', async () => {
    stubFetch(problem(409, 'invalid-state', '사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)'))

    await expect(createLabelsHttp().remove('l1')).rejects.toMatchObject({ kind: 'conflict', message: '사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)' })
  })
})
