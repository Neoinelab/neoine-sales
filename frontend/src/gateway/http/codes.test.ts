import { afterEach, describe, expect, it, vi } from 'vitest'
import { createCodesHttp } from './codes'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const code = (over: Record<string, unknown> = {}) => ({
  id: 'c1',
  kind: 'status',
  key: 'prospecting',
  name: '기회발굴',
  order: 1,
  locked: true,
  outcome: 'open',
  probability_hint: null,
  ...over,
})

describe('codes over HTTP', () => {
  it('all reads GET /codes and maps both lists', async () => {
    const { calls } = stubFetch(
      json({ statuses: [code()], forecasts: [code({ id: 'c2', kind: 'forecast', key: 'best', name: 'Best', locked: false, probability_hint: '51–75' })] }),
    )

    const set = await createCodesHttp().all()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/codes' })
    expect(set.statuses[0]).toEqual({ id: 'c1', kind: 'status', key: 'prospecting', name: '기회발굴', order: 1, locked: true, outcome: 'open', probabilityHint: null })
    expect(set.forecasts[0]).toMatchObject({ key: 'best', probabilityHint: '51–75' })
  })

  it('list reads GET /codes/usage for the kind and keeps the usage count', async () => {
    const { calls } = stubFetch(json([code({ usage_count: 3 })]))

    const rows = await createCodesHttp().list('status')

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/codes/usage?kind=status' })
    expect(rows[0]).toMatchObject({ key: 'prospecting', usageCount: 3 })
  })

  it('list shows the server 403 for a non-admin', async () => {
    stubFetch(problem(403, 'forbidden', '이 작업을 수행할 권한이 없습니다.'))

    await expect(createCodesHttp().list('status')).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
  })

  it('create posts kind, name and the hint, and returns the new code', async () => {
    const { calls } = stubFetch(json(code({ id: 'c9', kind: 'forecast', key: 'upside', name: 'Upside', locked: false, usage_count: 0 }), 201))

    const created = await createCodesHttp().create({ kind: 'forecast', name: 'Upside', probabilityHint: '10–20' })

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/codes', body: { kind: 'forecast', name: 'Upside', probability_hint: '10–20' } })
    expect(created).toMatchObject({ id: 'c9', key: 'upside', usageCount: 0 })
  })

  it('create sends a null hint when none is given', async () => {
    const { calls } = stubFetch(json(code({ usage_count: 0 }), 201))

    await createCodesHttp().create({ kind: 'status', name: '보류' })

    expect(calls[0]?.body).toEqual({ kind: 'status', name: '보류', probability_hint: null })
  })

  it('create maps a duplicate name to a conflict with the server message', async () => {
    stubFetch(problem(409, 'already-exists', '같은 이름의 코드가 이미 있습니다.'))

    await expect(createCodesHttp().create({ kind: 'status', name: '기회발굴' })).rejects.toMatchObject({
      status: 409,
      kind: 'conflict',
      message: '같은 이름의 코드가 이미 있습니다.',
    })
  })

  it('create maps a blank name to a validation error with the server message', async () => {
    stubFetch(problem(422, 'invalid-value', '이름을 입력하세요.'))

    await expect(createCodesHttp().create({ kind: 'status', name: '' })).rejects.toMatchObject({ kind: 'validation', message: '이름을 입력하세요.' })
  })

  it('rename patches the name', async () => {
    const { calls } = stubFetch(json(code({ name: '신규 발굴', usage_count: 0 })))

    const renamed = await createCodesHttp().rename('c1', '신규 발굴')

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/codes/c1', body: { name: '신규 발굴' } })
    expect(renamed.name).toBe('신규 발굴')
  })

  it('reorder puts the whole id list of the kind', async () => {
    const { calls } = stubFetch(json([code({ id: 'c2', order: 1, usage_count: 0 }), code({ id: 'c1', order: 2, usage_count: 0 })]))

    const rows = await createCodesHttp().reorder('status', ['c2', 'c1'])

    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/codes/order', body: { kind: 'status', ordered_ids: ['c2', 'c1'] } })
    expect(rows.map((r) => r.id)).toEqual(['c2', 'c1'])
  })

  it('reorder shows the server message for a wrong id list', async () => {
    stubFetch(problem(422, 'invalid-value', '순서 목록이 올바르지 않습니다.'))

    await expect(createCodesHttp().reorder('status', ['c1'])).rejects.toMatchObject({ kind: 'validation', message: '순서 목록이 올바르지 않습니다.' })
  })

  it('remove deletes and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createCodesHttp().remove('c1')).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/codes/c1' })
  })

  it.each([
    '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.',
    '사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)',
  ])('remove maps "%s" to a conflict', async (detail) => {
    stubFetch(problem(409, 'invalid-state', detail))

    await expect(createCodesHttp().remove('c1')).rejects.toMatchObject({ status: 409, kind: 'conflict', message: detail })
  })

  it('rejects an outcome the screens do not know', async () => {
    stubFetch(json({ statuses: [], forecasts: [code({ kind: 'forecast', outcome: 'weird' })] }))

    await expect(createCodesHttp().all()).rejects.toMatchObject({ message: '서버 응답을 해석할 수 없습니다.' })
  })
})
