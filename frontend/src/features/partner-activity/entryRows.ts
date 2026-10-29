/** 미팅 내용 입력 팝업의 행 상태와 검증(순수 로직). 서버 규칙의 정본은 서버이고, 여기서는 빠진 칸을 먼저 알려 준다. */

import { dateValueError, isDateValue } from '../../shared/model/dateText'
import type { PartnerMeetingInput } from '../../shared/model/types'

export const MAX_ROWS = 50

export type EntryField = 'partnerCompany' | 'dealCode' | 'meetingDate' | 'content'
export type EntryErrors = Partial<Record<EntryField, string>>
export type RowErrors = Record<number, EntryErrors>

export interface EntryRow {
  key: string
  /** 입력 칸에 보이는 글자. */
  partnerText: string
  /** 목록에서 고른 회사(직접 친 글자만으로는 채워지지 않는다). */
  partnerCompany: string
  dealText: string
  /** 목록에서 고른 Deal code. */
  dealCode: string
  /** 'YYYY-MM-DD' 또는 입력 중 글자. */
  meetingDate: string
  content: string
}

let sequence = 0

export function emptyRow(today: string): EntryRow {
  sequence += 1
  return { key: `row-${sequence}`, partnerText: '', partnerCompany: '', dealText: '', dealCode: '', meetingDate: today, content: '' }
}

/** 날짜는 보지 않는다(기본값이 들어 있다). 내용은 공백만이면 빈 것이다. */
export function isBlank(row: EntryRow): boolean {
  return row.partnerText === '' && row.partnerCompany === '' && row.dealText === '' && row.dealCode === '' && row.content.trim() === ''
}

export function firstMissingField(row: EntryRow): EntryField | null {
  if (row.partnerCompany === '') return 'partnerCompany'
  if (row.dealCode === '') return 'dealCode'
  if (!isDateValue(row.meetingDate)) return 'meetingDate'
  if (row.content.trim() === '') return 'content'
  return null
}

export function isComplete(row: EntryRow): boolean {
  return firstMissingField(row) === null
}

/** 한 행의 칸별 오류(빈 행도 검사한다). 수정 팝업이 쓴다. */
export function rowErrors(row: EntryRow): EntryErrors {
  const errors: EntryErrors = {}
  if (row.partnerCompany === '') errors.partnerCompany = '파트너를 선택하세요.'
  if (row.dealCode === '') errors.dealCode = 'Deal을 선택하세요.'
  if (row.meetingDate === '') errors.meetingDate = '미팅 날짜를 입력하세요.'
  else {
    const dateError = dateValueError(row.meetingDate)
    if (dateError) errors.meetingDate = dateError
  }
  if (row.content.trim() === '') errors.content = '미팅 내용을 입력하세요.'
  return errors
}

/** 빈 행은 건너뛰고, 그 밖의 행은 칸별 오류를 모은다. 키는 주어진 행 목록에서의 위치. */
export function validateRows(rows: readonly EntryRow[]): RowErrors {
  const result: RowErrors = {}
  rows.forEach((row, index) => {
    if (isBlank(row)) return
    const errors = rowErrors(row)
    if (Object.keys(errors).length > 0) result[index] = errors
  })
  return result
}

/** 빈 행을 뺀 요청 항목과, 각 항목이 화면의 몇 번째 행이었는지. */
export function rowsToInputs(rows: readonly EntryRow[]): { inputs: PartnerMeetingInput[]; rowIndexOf: number[] } {
  const inputs: PartnerMeetingInput[] = []
  const rowIndexOf: number[] = []
  rows.forEach((row, index) => {
    if (isBlank(row)) return
    inputs.push({ partnerCompany: row.partnerCompany, dealCode: row.dealCode, meetingDate: row.meetingDate, content: row.content })
    rowIndexOf.push(index)
  })
  return { inputs, rowIndexOf }
}

const WIRE_FIELDS: Readonly<Record<string, EntryField>> = {
  partner_company: 'partnerCompany',
  deal_code: 'dealCode',
  meeting_date: 'meetingDate',
  content: 'content',
}

/** 서버가 알려 준 위치(`['items', i, 필드]`)를 화면 행·칸으로 옮긴다. 필드마다 첫 문구만 두고, 놓을 수 없는 위치는 무시한다. */
export function applyServerErrors(itemErrors: readonly { location: readonly (string | number)[]; message: string }[], rowIndexOf: readonly number[]): RowErrors {
  const result: RowErrors = {}
  for (const { location, message } of itemErrors) {
    const [head, itemIndex, wire] = location
    if (head !== 'items' || typeof itemIndex !== 'number' || typeof wire !== 'string') continue
    const rowIndex = rowIndexOf[itemIndex]
    const field = WIRE_FIELDS[wire]
    if (rowIndex === undefined || field === undefined) continue
    const errors = (result[rowIndex] ??= {})
    errors[field] ??= message
  }
  return result
}
