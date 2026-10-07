/** 백엔드의 RFC 9457 problem+json 오류를 다루는 도구. */

export interface Problem {
  type: string
  title: string
  status: number
  detail: string
  errors?: { loc: (string | number)[]; msg: string }[]
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
}

function describeProblem(status: number, problem?: Problem): string {
  if (!problem) return `요청에 실패했습니다 (${status})`
  const fields = problem.errors?.map((e) => `${e.loc.slice(1).join('.')}: ${e.msg}`) ?? []
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
