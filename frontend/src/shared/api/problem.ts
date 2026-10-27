/** 백엔드의 RFC 9457 problem+json 오류를 다루는 도구. */

import type { ReportIssue } from '../model/reportTypes'

export interface Problem {
  type: string
  title: string
  status: number
  detail: string
  errors?: { loc: (string | number)[]; msg: string }[]
  /** invalid-report(리포트 정의 위반) 문제의 위반 목록. HTTP 어댑터가 서버의 `errors`에서 옮겨 담는다. */
  reportErrors?: ReportIssue[]
  /** directory-verification-failed 등이 싣는 실패 단계(connect·tls·bind·search). */
  stage?: string
}

function isProblem(value: unknown): value is Problem {
  return typeof value === 'object' && value !== null && 'type' in value && 'detail' in value
}

export class ApiError extends Error {
  readonly status: number
  readonly problem?: Problem

  constructor(status: number, problem?: Problem) {
    super(describeProblem(status, problem))
    this.status = status
    this.problem = problem
  }

  /** problem type의 마지막 조각(예: not-found, invalid-state). */
  get kind(): string | undefined {
    return this.problem?.type.split('/').pop()
  }

  /** AD 연결 검증이 실패한 단계(없으면 undefined). */
  get stage(): string | undefined {
    return this.problem?.stage
  }
}

function describeProblem(status: number, problem?: Problem): string {
  if (!problem && status === 403) return '이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.'
  if (!problem) return `요청에 실패했습니다 (${status})`
  // 서버가 loc 없는 항목을 실을 수 있으므로(invalid-report의 location/code/message) loc 배열이 있는 항목만 쓴다.
  const fields = problem.errors?.filter((e) => Array.isArray(e.loc)).map((e) => `${e.loc.slice(1).join('.')}: ${e.msg}`) ?? []
  return fields.length > 0 ? `${problem.detail} — ${fields.join(', ')}` : problem.detail
}

interface FetchResult<T> {
  data?: T
  error?: unknown
  response: Response
}

/** openapi-fetch 결과를 풀어 데이터를 돌려주고, 실패하면 ApiError를 던진다. */
export async function call<T>(request: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await request
  if (!response.ok) throw new ApiError(response.status, isProblem(error) ? error : undefined)
  return data as T
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return '네트워크 오류가 발생했습니다. 잠시 후 다시 시도하세요.'
}
