import { api } from '../../shared/api/client'
import { ApiError } from '../../shared/api/problem'
import type { ReportIssue } from '../../shared/model/reportTypes'
import type { ReportsGateway } from '../types'
import { toChartBody } from './mappers/reportChart'
import { toCatalog, toLayoutBody, toQueryBody, toResult, toSavedReport, toSummary } from './mappers/report'
import { malformedResponse, networkError, toApiError, unwrap } from './request'

const INVALID_REPORT_KIND = 'invalid-report'
const CONFLICT_STATUS = 409

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

function isProblemBody(body: unknown): body is { type: string; detail: string } {
  return typeof body === 'object' && body !== null && typeof (body as { type?: unknown }).type === 'string' && typeof (body as { detail?: unknown }).detail === 'string'
}

/**
 * 실패 본문을 ApiError로 바꾼다.
 * - invalid-report의 `errors`는 요청 검증 오류(`loc`/`msg`)와 모양이 달라 일반 변환에 넘기면 메시지 조립에서 깨지므로,
 *   위반 항목은 `reportErrors`로 옮기고 `errors`는 뺀 본문으로 변환한다.
 * - 409는 화면이 이름 중복(`already-exists`)과 저장 충돌(`invalid-state`)을 구분해야 하므로 서버 kind를 그대로 둔다
 *   (다른 어댑터의 `conflict` 정규화는 그대로).
 */
function toReportError(status: number, body: unknown): ApiError {
  if (status === CONFLICT_STATUS && isProblemBody(body)) return new ApiError(status, { title: 'Conflict', status, ...body })
  if (!isProblemBody(body) || body.type.split('/').pop() !== INVALID_REPORT_KIND) return toApiError(status, body)
  const { errors, ...rest } = body as { errors?: unknown } & Record<string, unknown>
  const base = toApiError(status, rest)
  const reportErrors = Array.isArray(errors) ? errors.filter(isIssue).map((e) => ({ location: [...e.location], code: e.code, message: e.message })) : []
  return base.problem ? new ApiError(status, { ...base.problem, reportErrors }) : base
}

interface Settled<T> {
  data?: T
  error?: unknown
  response: Response
}

/** 요청을 보내고 실패를 ApiError로 던진다. 성공이면 본문(204는 undefined)을 돌려준다. */
async function send<T>(request: Promise<Settled<T>>): Promise<T | undefined> {
  let result: Settled<T>
  try {
    result = await request
  } catch {
    throw networkError()
  }
  if (!result.response.ok) throw toReportError(result.response.status, result.error)
  return result.data
}

async function sendBody<T>(request: Promise<Settled<T>>): Promise<T> {
  const data = await send(request)
  if (data === undefined) throw malformedResponse()
  return data
}

export function createReportsHttp(): ReportsGateway {
  return {
    fields: async () => toCatalog(await unwrap(api.GET('/api/v1/reports/fields'))),
    query: async (input) => toResult(await sendBody(api.POST('/api/v1/reports/query', { body: toQueryBody(input) }))),
    list: async () => (await sendBody(api.GET('/api/v1/reports'))).map(toSummary),
    get: async (id) => toSavedReport(await sendBody(api.GET('/api/v1/reports/{report_id}', { params: { path: { report_id: id } } }))),
    create: async (input) =>
      toSavedReport(
        await sendBody(
          api.POST('/api/v1/reports', {
            body: { name: input.name, description: input.description, visibility: input.visibility, definition: toQueryBody(input.definition), chart: input.chart ? toChartBody(input.chart) : null, layout: toLayoutBody(input.layout) },
          }),
        ),
      ),
    update: async (id, input) =>
      toSavedReport(
        await sendBody(
          api.PUT('/api/v1/reports/{report_id}', {
            params: { path: { report_id: id } },
            body: {
              name: input.name,
              description: input.description,
              visibility: input.visibility,
              definition: toQueryBody(input.definition),
              chart: input.chart ? toChartBody(input.chart) : null,
              layout: toLayoutBody(input.layout),
              revision: input.revision,
            },
          }),
        ),
      ),
    copy: async (id, meta) =>
      toSavedReport(
        await sendBody(
          api.POST('/api/v1/reports/{report_id}/copy', {
            params: { path: { report_id: id } },
            body: { name: meta.name, description: meta.description, visibility: meta.visibility },
          }),
        ),
      ),
    remove: async (id) => {
      await send(api.DELETE('/api/v1/reports/{report_id}', { params: { path: { report_id: id } } }))
    },
    saveReportLayout: async (id, input) =>
      toSavedReport(
        await sendBody(
          api.PUT('/api/v1/reports/{report_id}/layout', {
            params: { path: { report_id: id } },
            body: { layout: toLayoutBody(input.layout), revision: input.revision },
          }),
        ),
      ),
    run: async (id) => toResult(await sendBody(api.POST('/api/v1/reports/{report_id}/run', { params: { path: { report_id: id } } }))),
  }
}
