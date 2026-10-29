import { api } from '../../shared/api/client'
import { ApiError } from '../../shared/api/problem'
import type { PartnerMeetingsGateway } from '../types'
import { toDealOption, toMeetingBody, toPartnerMeeting, toWireSort } from './mappers/partnerMeeting'
import { malformedResponse, networkError, toApiError } from './request'

interface Located {
  location: (string | number)[]
  message: string
}

function isLocated(value: unknown): value is Located {
  if (typeof value !== 'object' || value === null) return false
  const item = value as { location?: unknown; message?: unknown }
  return (
    Array.isArray(item.location) &&
    item.location.every((part) => typeof part === 'string' || typeof part === 'number') &&
    typeof item.message === 'string'
  )
}

/**
 * 실패 본문을 ApiError로 바꾼다. 422 `invalid-value`의 `errors[{location,message}]`는 요청 검증 오류(`loc`/`msg`)와 모양이 달라
 * 일반 변환에 넘기면 메시지에 필드 접미사가 붙으므로 `itemErrors`로 옮기고 `errors`는 뺀 본문으로 변환한다.
 */
function toMeetingError(status: number, body: unknown): ApiError {
  const isInvalidValue = typeof body === 'object' && body !== null && String((body as { type?: unknown }).type).split('/').pop() === 'invalid-value'
  if (!isInvalidValue || !Array.isArray((body as { errors?: unknown }).errors)) return toApiError(status, body)
  const { errors, ...rest } = body as { errors: unknown[] } & Record<string, unknown>
  const base = toApiError(status, rest)
  const itemErrors = errors.filter(isLocated).map((e) => ({ location: [...e.location], message: e.message }))
  return base.problem && itemErrors.length > 0 ? new ApiError(status, { ...base.problem, itemErrors }) : base
}

interface Settled<T> {
  data?: T
  error?: unknown
  response: Response
}

async function send<T>(request: Promise<Settled<T>>): Promise<T | undefined> {
  let result: Settled<T>
  try {
    result = await request
  } catch {
    throw networkError()
  }
  if (!result.response.ok) throw toMeetingError(result.response.status, result.error)
  return result.data
}

async function sendData<T>(request: Promise<Settled<T>>): Promise<T> {
  const data = await send(request)
  if (data === undefined) throw malformedResponse()
  return data
}

export function createPartnerMeetingsHttp(): PartnerMeetingsGateway {
  return {
    list: async (query, offset, limit) => {
      // 값이 있는 조건만 보낸다(서버 기본값을 쓴다).
      const params = {
        ...(query.partner ? { partner: query.partner } : {}),
        ...(query.deal ? { deal: query.deal } : {}),
        ...(query.content ? { content: query.content } : {}),
        ...(query.dateFrom ? { date_from: query.dateFrom } : {}),
        ...(query.dateTo ? { date_to: query.dateTo } : {}),
        ...(query.authorId !== undefined ? { author_user_id: query.authorId } : {}),
        sort: toWireSort(query.sort),
        order: query.order,
        offset,
        limit,
      }
      const page = await sendData(api.GET('/api/v1/partner-meetings', { params: { query: params } }))
      return { items: page.items.map(toPartnerMeeting), total: page.total, offset: page.offset, limit: page.limit }
    },
    create: async (items) => {
      const result = await sendData(api.POST('/api/v1/partner-meetings', { body: { items: items.map(toMeetingBody) } }))
      return result.items.map(toPartnerMeeting)
    },
    update: async (id, input) =>
      toPartnerMeeting(
        await sendData(api.PUT('/api/v1/partner-meetings/{meeting_id}', { params: { path: { meeting_id: id } }, body: toMeetingBody(input) })),
      ),
    remove: async (id) => {
      await send(api.DELETE('/api/v1/partner-meetings/{meeting_id}', { params: { path: { meeting_id: id } } }))
    },
    dealOptions: async (company) =>
      (await sendData(api.GET('/api/v1/partner-meetings/deal-options', { params: { query: { company } } }))).items.map(toDealOption),
  }
}
