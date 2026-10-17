/**
 * 생성된 클라이언트(openapi-fetch)의 결과를 게이트웨이 계약으로 바꾼다.
 * - 성공이면 본문(또는 204의 undefined)을 돌려준다.
 * - 실패는 모두 `ApiError`로 던진다. problem의 `detail`은 서버 문구 그대로이고, `type`의 kind만 게이트웨이 표기로 정규화한다.
 * - 서버에 닿지 못하면 `ApiError(0)`(네트워크 오류 원문은 숨긴다).
 */

import { ApiError, type Problem } from '../../shared/api/problem'

const PROBLEM_BASE = 'https://sales.neoine.test/problems/'
export const NETWORK_MESSAGE = '서버에 연결할 수 없습니다.'
export const MALFORMED_MESSAGE = '서버 응답을 해석할 수 없습니다.'

/** 서버 kind → 게이트웨이 kind. 표에 없는 kind(forbidden, not-found, directory-* …)는 그대로 둔다. */
const KIND_MAP: Readonly<Record<string, string>> = {
  'invalid-value': 'validation',
  'request-validation': 'validation',
  'invalid-reference': 'validation',
  'already-exists': 'conflict',
  'invalid-state': 'conflict',
  unauthenticated: 'unauthorized',
}

export function normalizeKind(serverKind: string): string {
  return KIND_MAP[serverKind] ?? serverKind
}

interface Result<T> {
  data?: T
  error?: unknown
  response: Response
}

function isProblem(value: unknown): value is Problem {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as { type?: unknown }).type === 'string' &&
    typeof (value as { detail?: unknown }).detail === 'string'
  )
}

/** HTTP 상태와 응답 본문(problem이면 kind 정규화)으로 ApiError를 만든다. */
export function toApiError(status: number, body: unknown): ApiError {
  if (!isProblem(body)) return new ApiError(status)
  const kind = normalizeKind(body.type.split('/').pop() ?? '')
  return new ApiError(status, { ...body, type: `${PROBLEM_BASE}${kind}` })
}

export function networkError(): ApiError {
  return new ApiError(0, {
    type: `${PROBLEM_BASE}network`,
    title: 'Network Error',
    status: 0,
    detail: NETWORK_MESSAGE,
  })
}

/** 서버 응답이 계약과 다를 때(알 수 없는 값 등). 화면이 읽을 수 있는 문구로 던진다. */
export function malformedResponse(): ApiError {
  return new ApiError(502, {
    type: `${PROBLEM_BASE}malformed-response`,
    title: 'Malformed Response',
    status: 502,
    detail: MALFORMED_MESSAGE,
  })
}

export async function settle<T>(request: Promise<Result<T>>): Promise<Result<T>> {
  let result: Result<T>
  try {
    result = await request
  } catch {
    throw networkError()
  }
  if (!result.response.ok) throw toApiError(result.response.status, result.error)
  return result
}

/** 본문이 있는 성공 응답의 데이터. */
export async function unwrap<T>(request: Promise<Result<T>>): Promise<T> {
  const { data } = await settle(request)
  if (data === undefined) throw malformedResponse()
  return data
}

/** 본문이 없는 성공 응답(204). */
export async function unwrapVoid(request: Promise<Result<unknown>>): Promise<void> {
  await settle(request)
}
