import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/problem'
import { api } from '../../shared/api/client'
import { json, noContent, problem, stubFetch, stubNetworkDown } from './testHelpers'
import { normalizeKind, unwrap, unwrapVoid } from './request'

afterEach(() => vi.unstubAllGlobals())

const ME = { user_id: 1, subject: 'kim', name: '김영업', role: 'sales', email: null }

describe('normalizeKind', () => {
  it.each([
    ['invalid-value', 'validation'],
    ['request-validation', 'validation'],
    ['invalid-reference', 'validation'],
    ['already-exists', 'conflict'],
    ['invalid-state', 'conflict'],
    ['unauthenticated', 'unauthorized'],
    ['not-found', 'not-found'],
    ['forbidden', 'forbidden'],
    ['directory-verification-failed', 'directory-verification-failed'],
  ])('maps %s to %s', (server, expected) => {
    expect(normalizeKind(server)).toBe(expected)
  })
})

describe('unwrap', () => {
  it('returns the body of a successful response', async () => {
    stubFetch(json(ME))

    await expect(unwrap(api.GET('/api/v1/auth/me'))).resolves.toEqual(ME)
  })

  it('sends the CSRF header and credentials on every request', async () => {
    const { calls } = stubFetch(json(ME))

    await unwrap(api.GET('/api/v1/auth/me'))

    expect(calls[0]?.headers.get('X-Requested-With')).toBe('neoine-web')
    expect(calls[0]?.credentials).toBe('include')
  })

  it('throws an ApiError with the gateway kind and the server detail', async () => {
    stubFetch(problem(409, 'already-exists', '같은 이름의 코드가 이미 있습니다.'))

    const failure = unwrap(api.GET('/api/v1/auth/me'))

    await expect(failure).rejects.toBeInstanceOf(ApiError)
    await expect(failure).rejects.toMatchObject({ status: 409, kind: 'conflict', message: '같은 이름의 코드가 이미 있습니다.' })
  })

  it.each([
    [401, 'unauthenticated', 'unauthorized'],
    [403, 'forbidden', 'forbidden'],
    [404, 'not-found', 'not-found'],
    [422, 'invalid-value', 'validation'],
    [422, 'request-validation', 'validation'],
    [409, 'invalid-state', 'conflict'],
  ])('status %i %s becomes kind %s', async (status, serverKind, kind) => {
    stubFetch(problem(status, serverKind, '서버 문구'))

    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })

  it('keeps the stage of a directory verification failure', async () => {
    stubFetch(problem(422, 'directory-verification-failed', '연결 실패', { stage: 'bind' }))

    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toMatchObject({ kind: 'directory-verification-failed', stage: 'bind' })
  })

  it('keeps the field errors of a request validation problem in the message', async () => {
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', { errors: [{ loc: ['body', 'name'], msg: 'Field required' }] }))

    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toThrow('name: Field required')
  })

  it('gives a readable message when the failure body is not a problem document', async () => {
    stubFetch(new Response('<html>Bad Gateway</html>', { status: 502 }))

    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toMatchObject({ status: 502, message: '요청에 실패했습니다 (502)' })
  })

  it('explains an unreachable server instead of leaking the network error', async () => {
    stubNetworkDown()

    const failure = unwrap(api.GET('/api/v1/auth/me'))

    await expect(failure).rejects.toBeInstanceOf(ApiError)
    await expect(failure).rejects.toMatchObject({ status: 0, message: '서버에 연결할 수 없습니다.' })
  })
})

describe('unwrapVoid', () => {
  it('resolves for a 204 without a body', async () => {
    stubFetch(noContent())

    await expect(unwrapVoid(api.POST('/api/v1/auth/logout'))).resolves.toBeUndefined()
  })

  it('throws the normalized error for a failure', async () => {
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'))

    await expect(unwrapVoid(api.POST('/api/v1/auth/logout'))).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
  })
})
