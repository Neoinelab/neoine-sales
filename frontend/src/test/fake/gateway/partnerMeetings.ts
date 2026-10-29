/**
 * 파트너 Activity(미팅 기록) Fake. 서버 규칙을 그대로 따른다.
 * - 읽기는 로그인한 모든 역할, 입력·수정·삭제는 sales·admin(user는 403), 수정·삭제는 작성자 본인 또는 admin
 * - 회사는 저장 시점의 대표 표기 텍스트(등록된 파트너 연락처 회사명, 대소문자 무시로 해석)
 * - Deal 선택지는 지금 활성 파트너 링크의 연락처 회사가 같은 Deal 전부(Won·Lost 포함)
 * - 일괄 입력은 원자적이고 위반을 모두 모아 `problem.itemErrors`(위치 + 문구)로 던진다(422)
 * - 판정 순서: 401 -> 403(역할) -> 404 -> 403(작성자) -> 422
 */

import { ApiError } from '../../../shared/api/problem'
import type { PartnerMeetingsGateway } from '../../../gateway/types'
import { isDateValue } from '../../../shared/model/dateText'
import type { PartnerDealOption, PartnerMeeting, PartnerMeetingInput, PartnerMeetingQuery, Role } from '../../../shared/model/types'
import { forbidden, notFound, validation } from '../errors'
import { takeId, type PartnerMeetingRecord, type SeedData } from '../store'
import { read, requireUser, requireWrite, write, type MockContext } from './context'
import { userRef } from './views'

export const COMPANY_NOT_FOUND = '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.'
export const DEAL_NOT_FOUND = 'Deal을 찾을 수 없습니다. 목록에서 다시 선택하세요.'
export const DEAL_NOT_LINKED = '선택한 파트너와 연결된 Deal이 아닙니다.'
export const CONTENT_REQUIRED = '미팅 내용을 입력하세요.'
export const NO_ITEMS = '입력한 미팅이 없습니다.'
export const TOO_MANY_ITEMS = '한 번에 50건까지 입력할 수 있습니다.'
export const EDIT_FORBIDDEN = '본인 미팅 기록 또는 admin만 수정할 수 있습니다.'
export const DELETE_FORBIDDEN = '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.'
export const MEETING_NOT_FOUND = '미팅 기록을 찾을 수 없습니다.'
export const DATE_RANGE_REVERSED = '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.'
export const DATE_OUT_OF_BOUNDS = '미팅 날짜은(는) 1900-01-01부터 2999-12-31 사이여야 합니다'
const MAX_ITEMS = 50
const MIN_DATE = '1900-01-01'
const MAX_DATE = '2999-12-31'
const PROBLEM_BASE = 'https://sales.neoine.test/problems/'

type Field = 'partner_company' | 'deal_code' | 'meeting_date' | 'content'
interface Issue {
  location: (string | number)[]
  message: string
}

const lower = (text: string): string => text.toLowerCase()

/** 서버의 `invalid-value`(errors[].location) 응답: detail은 첫 위반 문구, 위반 전체는 itemErrors. */
function invalid(issues: Issue[]): ApiError {
  return new ApiError(422, {
    type: `${PROBLEM_BASE}validation`,
    title: 'Unprocessable Entity',
    status: 422,
    detail: issues[0]?.message ?? '입력이 올바르지 않습니다.',
    itemErrors: issues,
  })
}

/** 등록된 파트너 회사(연락처 회사명의 대표 표기, 대소문자 무시로 묶음). */
function partnerCompanies(data: SeedData): string[] {
  const first = new Map<string, string>()
  const ordered = data.contacts.filter((c) => c.kind === 'partner').sort((a, b) => a.createdAt.localeCompare(b.createdAt) || a.id - b.id)
  for (const contact of ordered) if (!first.has(lower(contact.company))) first.set(lower(contact.company), contact.company)
  return [...first.values()].sort((a, b) => (lower(a) < lower(b) ? -1 : lower(a) > lower(b) ? 1 : 0))
}

function resolveCompany(data: SeedData, raw: string): string | null {
  return partnerCompanies(data).find((c) => lower(c) === lower(raw)) ?? null
}

/** 지금 활성 파트너 링크의 연락처 회사가 같은 Deal(이름 소문자 -> code 순). */
function linkedDeals(data: SeedData, company: string): PartnerDealOption[] {
  const wanted = lower(company)
  return data.deals
    .filter((deal) =>
      deal.partnerLinks.some((link) => link.active && lower(data.contacts.find((c) => c.id === link.contactId)?.company ?? '') === wanted),
    )
    .map((deal) => ({
      code: deal.code,
      name: deal.name,
      customerCompany: data.contacts.find((c) => c.id === deal.customerContactId)?.company ?? '',
    }))
    .sort((a, b) => (lower(a.name) < lower(b.name) ? -1 : lower(a.name) > lower(b.name) ? 1 : a.code < b.code ? -1 : 1))
}

function dateIssue(day: string): string | null {
  if (day < MIN_DATE || day > MAX_DATE) return DATE_OUT_OF_BOUNDS
  return isDateValue(day) ? null : '날짜 형식이 올바르지 않습니다.'
}

interface Checked {
  company: string
  dealCode: string
  meetingDate: string
  content: string
}

/** 한 행 검사. 순서는 회사 -> Deal -> 날짜 -> 내용이고 회사가 틀리면 그 행의 Deal 검사만 건너뛴다. */
function checkRow(data: SeedData, input: PartnerMeetingInput, at: (field: Field) => (string | number)[], link: boolean): { checked: Checked | null; issues: Issue[] } {
  const issues: Issue[] = []
  const company = resolveCompany(data, input.partnerCompany)
  if (link) {
    if (company === null) issues.push({ location: at('partner_company'), message: COMPANY_NOT_FOUND })
    else {
      const exists = data.deals.some((d) => d.code === input.dealCode)
      if (!exists) issues.push({ location: at('deal_code'), message: DEAL_NOT_FOUND })
      else if (!linkedDeals(data, company).some((d) => d.code === input.dealCode)) issues.push({ location: at('deal_code'), message: DEAL_NOT_LINKED })
    }
  }
  const dateMessage = dateIssue(input.meetingDate)
  if (dateMessage) issues.push({ location: at('meeting_date'), message: dateMessage })
  const content = input.content.trim()
  if (content === '') issues.push({ location: at('content'), message: CONTENT_REQUIRED })
  if (issues.length > 0) return { checked: null, issues }
  return { checked: { company: company ?? input.partnerCompany, dealCode: input.dealCode, meetingDate: input.meetingDate, content }, issues }
}

function view(data: SeedData, record: PartnerMeetingRecord): PartnerMeeting {
  const deal = data.deals.find((d) => d.code === record.dealCode)
  return {
    id: record.id,
    partnerCompany: record.partnerCompany,
    deal: { code: record.dealCode, name: deal?.name ?? record.dealCode },
    meetingDate: record.meetingDate,
    content: record.content,
    author: userRef(data, record.authorId),
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  }
}

function records(data: SeedData): PartnerMeetingRecord[] {
  data.partnerMeetings ??= []
  return data.partnerMeetings
}

function canEdit(role: Role, userId: number, authorId: number): boolean {
  return role === 'admin' || (role === 'sales' && userId === authorId)
}

function matches(data: SeedData, record: PartnerMeetingRecord, query: PartnerMeetingQuery): boolean {
  const deal = data.deals.find((d) => d.code === record.dealCode)
  const has = (hay: string, needle: string | undefined): boolean => !needle?.trim() || lower(hay).includes(lower(needle.trim()))
  return (
    has(record.partnerCompany, query.partner) &&
    (!query.deal?.trim() || lower(deal?.name ?? '').includes(lower(query.deal.trim())) || lower(record.dealCode).includes(lower(query.deal.trim()))) &&
    has(record.content, query.content) &&
    (!query.dateFrom || record.meetingDate >= query.dateFrom) &&
    (!query.dateTo || record.meetingDate <= query.dateTo) &&
    (query.authorId === undefined || record.authorId === query.authorId)
  )
}

/** 정렬: 날짜 열은 (날짜, id)를 방향대로, 텍스트 열은 소문자 값을 방향대로 두고 동률은 방향과 무관하게 날짜 내림차순 -> id 내림차순. */
function sorted(data: SeedData, found: PartnerMeetingRecord[], query: PartnerMeetingQuery): PartnerMeetingRecord[] {
  const sign = query.order === 'asc' ? 1 : -1
  const newestFirst = (a: PartnerMeetingRecord, b: PartnerMeetingRecord): number => (a.meetingDate === b.meetingDate ? b.id - a.id : a.meetingDate < b.meetingDate ? 1 : -1)
  if (query.sort === 'meetingDate') {
    return [...found].sort((a, b) => sign * (a.meetingDate === b.meetingDate ? a.id - b.id : a.meetingDate < b.meetingDate ? -1 : 1))
  }
  const key = (r: PartnerMeetingRecord): string => {
    switch (query.sort) {
      case 'partner':
        return lower(r.partnerCompany)
      case 'deal':
        return lower(data.deals.find((d) => d.code === r.dealCode)?.name ?? '')
      case 'content':
        return lower(r.content)
      default:
        return lower(userRef(data, r.authorId).name)
    }
  }
  return [...found].sort((a, b) => {
    const x = key(a)
    const y = key(b)
    return x === y ? newestFirst(a, b) : sign * (x < y ? -1 : 1)
  })
}

export function createPartnerMeetingsGateway(ctx: MockContext): PartnerMeetingsGateway {
  return {
    list: (query, offset, limit) =>
      read(ctx, () => {
        requireUser(ctx)
        const data = ctx.store.data
        if (query.dateFrom && query.dateTo && query.dateFrom > query.dateTo) throw validation(DATE_RANGE_REVERSED)
        const found = sorted(data, records(data).filter((r) => matches(data, r, query)), query)
        return { items: found.slice(offset, offset + limit).map((r) => view(data, r)), total: found.length, offset, limit }
      }),
    create: (items) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const data = ctx.store.data
        if (items.length === 0) throw validation(NO_ITEMS)
        if (items.length > MAX_ITEMS) throw validation(TOO_MANY_ITEMS)
        const issues: Issue[] = []
        const checked: Checked[] = []
        items.forEach((input, index) => {
          const result = checkRow(data, input, (field) => ['items', index, field], true)
          issues.push(...result.issues)
          if (result.checked) checked.push(result.checked)
        })
        if (issues.length > 0) throw invalid(issues)
        const now = ctx.clock.now()
        const created = checked.map((c): PartnerMeetingRecord => ({
          id: takeId(data.counters, 'pm'),
          partnerCompany: c.company,
          dealCode: c.dealCode,
          meetingDate: c.meetingDate,
          content: c.content,
          authorId: user.id,
          createdAt: now,
          updatedAt: now,
        }))
        records(data).push(...created)
        return created.map((r) => view(data, r))
      }),
    update: (id, input) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const data = ctx.store.data
        const record = records(data).find((r) => r.id === id)
        if (!record) throw notFound(MEETING_NOT_FOUND)
        if (!canEdit(user.role, user.id, record.authorId)) throw forbidden(EDIT_FORBIDDEN)
        const companyChanged = lower(input.partnerCompany) !== lower(record.partnerCompany)
        const result = checkRow(data, input, (field) => [field], companyChanged || input.dealCode !== record.dealCode)
        if (!result.checked) throw invalid(result.issues)
        const company = companyChanged ? result.checked.company : record.partnerCompany
        const changed =
          company !== record.partnerCompany ||
          result.checked.dealCode !== record.dealCode ||
          result.checked.meetingDate !== record.meetingDate ||
          result.checked.content !== record.content
        if (changed) {
          record.partnerCompany = company
          record.dealCode = result.checked.dealCode
          record.meetingDate = result.checked.meetingDate
          record.content = result.checked.content
          record.updatedAt = ctx.clock.now()
        }
        return view(data, record)
      }),
    remove: (id) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const data = ctx.store.data
        const record = records(data).find((r) => r.id === id)
        if (!record) throw notFound(MEETING_NOT_FOUND)
        if (!canEdit(user.role, user.id, record.authorId)) throw forbidden(DELETE_FORBIDDEN)
        data.partnerMeetings = records(data).filter((r) => r.id !== id)
      }),
    dealOptions: (company) =>
      read(ctx, () => {
        requireUser(ctx)
        const resolved = resolveCompany(ctx.store.data, company)
        return resolved === null ? [] : linkedDeals(ctx.store.data, resolved)
      }),
  }
}
