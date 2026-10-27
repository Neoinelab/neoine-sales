import { api } from '../../shared/api/client'
import { ApiError } from '../../shared/api/problem'
import type { ReportIssue } from '../../shared/model/reportTypes'
import type { ReportsGateway } from '../types'
import { toCatalog, toQueryBody, toResult } from './mappers/report'
import { malformedResponse, networkError, toApiError, unwrap } from './request'

const INVALID_REPORT_KIND = 'invalid-report'

function isIssue(value: unknown): value is ReportIssue {
  if (typeof value !== 'object' || value === null) return false
  const item = value as { location?: unknown; code?: unknown; message?: unknown }
  return (
    Array.isArray(item.location) &&
    item.location.every((part) => typeof part === 'string' || typeof part === 'number') &&
    typeof item.code === 'string' &&
    typeof item.message === 'string'
  )
}

/**
 * 조회 실패 본문을 ApiError로 바꾼다. invalid-report의 `errors`는 요청 검증 오류(`loc`/`msg`)와 모양이 달라
 * 일반 변환에 넘기면 메시지 조립에서 깨지므로, 위반 항목은 `reportErrors`로 옮기고 `errors`는 뺀 본문으로 변환한다.
 */
function toQueryError(status: number, body: unknown): ApiError {
  const isReportProblem =
    typeof body === 'object' &&
    body !== null &&
    typeof (body as { type?: unknown }).type === 'string' &&
    (body as { type: string }).type.split('/').pop() === INVALID_REPORT_KIND
  if (!isReportProblem) return toApiError(status, body)
  const { errors, ...rest } = body as { errors?: unknown } & Record<string, unknown>
  const base = toApiError(status, rest)
  const reportErrors = Array.isArray(errors) ? errors.filter(isIssue).map((e) => ({ location: [...e.location], code: e.code, message: e.message })) : []
  return base.problem ? new ApiError(status, { ...base.problem, reportErrors }) : base
}

const postQuery = (body: ReturnType<typeof toQueryBody>) => api.POST('/api/v1/reports/query', { body })

export function createReportsHttp(): ReportsGateway {
  return {
    fields: async () => toCatalog(await unwrap(api.GET('/api/v1/reports/fields'))),
    query: async (input) => {
      let result: Awaited<ReturnType<typeof postQuery>>
      try {
        result = await postQuery(toQueryBody(input))
      } catch {
        throw networkError()
      }
      if (!result.response.ok) throw toQueryError(result.response.status, result.error)
      if (result.data === undefined) throw malformedResponse()
      return toResult(result.data)
    },
  }
}
