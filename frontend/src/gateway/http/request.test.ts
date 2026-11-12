import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../shared/api/problem'
import { api } from '../../shared/api/client'
import { json, noContent, problem, stubFetch, stubNetworkDown } from './testHelpers'
import { normalizeKind, unwrap, unwrapVoid } from './request'

afterEach(() => vi.unstubAllGlobals())

const ME = { user_id: 1, subject: 'kim', name: '김영업', role: 'sales', email: null }

describe('normalizeKind', () => {
  // 서버 오류 종류를 화면 종류로 정규화한다.
  // 테스트 코드: PL-071
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
    // when: 화면 kind로 정규화한다 (전제: 서버 kind)
    const kind = normalizeKind(server)
    // then: 표의 화면 kind다
    expect(kind).toBe(expected)
  })
})

describe('unwrap', () => {
  // 성공 응답은 본문을 그대로 돌려준다.
  it('returns the body of a successful response', async () => {
    // given: 200과 본문을 돌려주는 가짜 서버
    stubFetch(json(ME))

    // when: 요청을 푼다
    const result = await unwrap(api.GET('/api/v1/auth/me'))
    // then: 본문을 그대로 돌려준다
    expect(result).toEqual(ME)
  })

  // 모든 API 요청은 CSRF 헤더와 쿠키를 함께 보낸다.
  // 테스트 코드: PL-066
  it('sends the CSRF header and credentials on every request', async () => {
    // given: 응답을 고정한 가짜 서버
    const { calls } = stubFetch(json(ME))
    // when: 생성된 API 클라이언트로 요청한다
    await unwrap(api.GET('/api/v1/auth/me'))
    // then: X-Requested-With 헤더가 있고 credentials가 include다
    expect(calls[0]?.headers.get('X-Requested-With')).toBe('neoine-web')
    expect(calls[0]?.credentials).toBe('include')
  })

  // 서버 Problem의 문구를 그대로 담은 ApiError를 던진다.
  // 테스트 코드: PL-067
  it('throws an ApiError with the gateway kind and the server detail', async () => {
    // given: 409 already-exists Problem
    stubFetch(problem(409, 'already-exists', '같은 이름의 코드가 이미 있습니다.'))
    // when: 요청한다
    const failure = unwrap(api.GET('/api/v1/auth/me'))
    // then: ApiError이고 화면 kind와 서버 문구를 가진다

    await expect(failure).rejects.toBeInstanceOf(ApiError)
    await expect(failure).rejects.toMatchObject({ status: 409, kind: 'conflict', message: '같은 이름의 코드가 이미 있습니다.' })
  })

  // 상태와 서버 kind가 화면 kind로 바뀌고 서버 문구는 그대로다.
  // 테스트 코드: PL-071
  it.each([
    [401, 'unauthenticated', 'unauthorized'],
    [403, 'forbidden', 'forbidden'],
    [404, 'not-found', 'not-found'],
    [422, 'invalid-value', 'validation'],
    [422, 'request-validation', 'validation'],
    [409, 'invalid-state', 'conflict'],
  ])('status %i %s becomes kind %s', async (status, serverKind, kind) => {
    // given: 그 상태와 kind의 Problem
    stubFetch(problem(status, serverKind, '서버 문구'))
    // when·then: 요청한다 → 화면 kind로 바뀐 ApiError를 던진다
    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })

  // directory-verification-failed는 stage를 유지한다.
  // 테스트 코드: PL-071
  it('keeps the stage of a directory verification failure', async () => {
    // given: stage가 있는 directory-verification-failed Problem
    stubFetch(problem(422, 'directory-verification-failed', '연결 실패', { stage: 'bind' }))
    // when·then: 요청한다 → kind와 stage가 유지된다
    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toMatchObject({ kind: 'directory-verification-failed', stage: 'bind' })
  })

  // 422 request-validation의 칸 오류를 문구에 붙인다.
  // 테스트 코드: PL-067
  it('keeps the field errors of a request validation problem in the message', async () => {
    // given: errors에 loc가 있는 422 Problem
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', { errors: [{ loc: ['body', 'name'], msg: 'Field required' }] }))

    // when·then: 요청한다 → 문구에 "name: Field required"가 붙는다
    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toThrow('name: Field required')
  })

  // Problem이 아닌 본문의 실패는 상태가 든 고정 문구를 보인다.
  // 테스트 코드: PL-068
  it('gives a readable message when the failure body is not a problem document', async () => {
    // given: Problem이 아닌 본문의 502 응답
    stubFetch(new Response('<html>Bad Gateway</html>', { status: 502 }))

    // when·then: 요청한다 → 상태 502와 "요청에 실패했습니다 (502)"다
    await expect(unwrap(api.GET('/api/v1/auth/me'))).rejects.toMatchObject({ status: 502, message: '요청에 실패했습니다 (502)' })
  })

  // 서버에 닿지 못하면 네트워크 원문 대신 고정 문구를 보인다.
  // 테스트 코드: PL-069
  it('explains an unreachable server instead of leaking the network error', async () => {
    // given: 네트워크가 끊긴 상태
    stubNetworkDown()
    // when: 요청한다
    const failure = unwrap(api.GET('/api/v1/auth/me'))

    await expect(failure).rejects.toBeInstanceOf(ApiError)
    // then: 상태 0의 ApiError이고 문구는 고정 문구다
    await expect(failure).rejects.toMatchObject({ status: 0, message: '서버에 연결할 수 없습니다.' })
  })

  // 본문이 있어야 하는 성공 응답에 본문이 없으면 502 해석 불가 오류다.
  // 테스트 코드: PL-072
  it('turns a success response without a body into an unreadable-response error', async () => {
    // given: 본문이 없는 200 응답(본문이 있어야 하는 요청)
    stubFetch(new Response(null, { status: 200, headers: { 'Content-Length': '0' } }))
    // when: 게이트웨이가 결과를 푼다
    const failure = unwrap(api.GET('/api/v1/auth/me'))
    // then: 상태 502, 문구 "서버 응답을 해석할 수 없습니다."의 ApiError다
    await expect(failure).rejects.toBeInstanceOf(ApiError)
    await expect(failure).rejects.toMatchObject({ status: 502, message: '서버 응답을 해석할 수 없습니다.' })
  })
})

describe('unwrapVoid', () => {
  // 본문 없는 204 요청은 성공으로 끝난다.
  // 테스트 코드: PL-072
  it('resolves for a 204 without a body', async () => {
    // given: 본문 없는 204 응답
    stubFetch(noContent())
    // when: 본문 없는 요청(로그아웃)을 푼다
    const result = await unwrapVoid(api.POST('/api/v1/auth/logout'))
    // then: 성공으로 끝난다
    expect(result).toBeUndefined()
  })

  // 실패 응답은 kind를 정규화한 ApiError를 던진다.
  it('throws the normalized error for a failure', async () => {
    // given: 403 forbidden Problem을 돌려주는 가짜 서버
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'))

    // when·then: 본문 없는 요청을 푼다 → 상태 403, kind forbidden 오류를 던진다
    await expect(unwrapVoid(api.POST('/api/v1/auth/logout'))).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
  })
})
