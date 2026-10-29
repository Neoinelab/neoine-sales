/** 파트너 Activity 화면 테스트 공용 도구(운영 코드에서 쓰지 않는다). DOM 계약은 `artifacts/20-agent-outputs/02-tests-part2-frontend.md`. */
import { screen, waitFor, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { defaultMock } from './fake/default'
import { SEED_MEETINGS } from './fixtures/partnerMeetings'

export const PAGE = '/partner-activities'
/** 시드 날짜를 고정하는 서버 시각. 시드 미팅 N일 전은 2027-03-15 - N일이다. */
export const NOW = '2027-03-15T10:00:00+09:00'
export const TODAY = '2027-03-15'
export const TODAY_TEXT = '2027.03.15'
/** 열 머리글 5개(정렬 가능). */
export const COLUMNS = ['파트너', 'Deal', '미팅 날짜', '미팅 내용', '작성자'] as const

/** 시계를 고정한다. 반드시 `renderAt` 전에 부르고 afterEach에서 `unpinClock`을 부른다. */
export function pinClock(): void {
  defaultMock.clock.setNow(NOW)
}
export function unpinClock(): void {
  defaultMock.clock.setNow(null)
}

export function meetingTable(): HTMLElement {
  return screen.getByRole('table', { name: '파트너 미팅 기록' })
}

/** 머리글 행을 뺀 데이터 행. */
export function meetingRows(): HTMLElement[] {
  return within(meetingTable()).getAllByRole('row').slice(1)
}

export function cellsOf(row: HTMLElement): HTMLElement[] {
  return within(row).getAllByRole('cell')
}

/** 현재 보이는 행의 미팅 내용(4번째 칸, textContent 그대로 = 줄바꿈 유지). */
export function shownContents(): string[] {
  return meetingRows().map((row) => cellsOf(row)[3]?.textContent ?? '')
}

export async function waitForRows(count: number): Promise<void> {
  await waitFor(() => expect(meetingRows()).toHaveLength(count))
}

/** 기본 목록 순서(미팅 날짜 내림차순)의 시드 내용. */
export const SEED_CONTENTS: readonly string[] = [...SEED_MEETINGS].reverse().map((m) => m[3])

export function paramsOf(location: string): URLSearchParams {
  return new URLSearchParams(location.split('?')[1] ?? '')
}

export function rowWithContent(content: string): HTMLElement {
  const found = meetingRows().find((row) => cellsOf(row)[3]?.textContent === content)
  if (!found) throw new Error(`내용이 "${content}"인 행이 없다`)
  return found
}

/** "미팅 내용 입력" 팝업을 연다. */
export async function openEntryDialog(user: UserEvent): Promise<HTMLElement> {
  await user.click(await screen.findByRole('button', { name: '미팅 내용 입력' }))
  return screen.findByRole('dialog', { name: '미팅 내용 입력' })
}

/** 팝업의 n번째(1부터) 행 요소. 행은 role=group, 이름 "미팅 n"이다. */
export function entryGroup(dialog: HTMLElement, n: number): HTMLElement {
  return within(dialog).getByRole('group', { name: `미팅 ${n}` })
}

/** 팝업의 n번째 행 안에서 질의한다. */
export function entryRow(dialog: HTMLElement, n: number) {
  return within(entryGroup(dialog, n))
}

/** 팝업 행의 칸들. `native`는 달력(숨은 input[type=date]). */
export function fieldsOf(dialog: HTMLElement, n: number) {
  const row = entryRow(dialog, n)
  return {
    partner: row.getByRole<HTMLInputElement>('combobox', { name: '파트너' }),
    deal: row.getByRole<HTMLInputElement>('combobox', { name: 'Deal' }),
    date: row.getByRole<HTMLInputElement>('textbox', { name: '미팅 날짜' }),
    content: row.getByRole<HTMLTextAreaElement>('textbox', { name: '미팅 내용' }),
    /** 입력 팝업 행에만 있다(수정 팝업에는 없으므로 접근할 때만 찾는다). */
    get remove() {
      return row.getByRole('button', { name: '행 삭제' })
    },
    native: entryGroup(dialog, n).querySelector<HTMLInputElement>('input[type="date"]') as HTMLInputElement,
  }
}

/** 파트너를 목록에서 골라 Deal 칸으로 이동시킨다. */
export async function choosePartner(user: UserEvent, dialog: HTMLElement, n: number, company: string): Promise<void> {
  const { partner } = fieldsOf(dialog, n)
  await user.click(partner)
  await user.click(await within(dialog).findByRole('option', { name: company }))
}

/** 열려 있는 Deal 목록에서 이름 일부로 하나를 골라 날짜 칸으로 이동시킨다(파트너를 먼저 골라야 한다). */
export async function chooseDeal(user: UserEvent, dialog: HTMLElement, name: RegExp | string): Promise<void> {
  await user.click(await within(dialog).findByRole('option', { name: typeof name === 'string' ? new RegExp(name) : name }))
}

export interface RowValues {
  company: string
  /** 목록에서 고를 Deal의 이름 일부. */
  deal: RegExp | string
  /** 'yyyymmdd'. 생략하면 기본값(오늘)을 둔다. */
  date?: string
  content: string
}

/** n번째 행을 파트너 -> Deal -> (날짜) -> 내용 순으로 채운다. */
export async function fillRow(user: UserEvent, dialog: HTMLElement, n: number, values: RowValues): Promise<void> {
  await choosePartner(user, dialog, n, values.company)
  await chooseDeal(user, dialog, values.deal)
  const { date, content } = fieldsOf(dialog, n)
  if (values.date) {
    await user.clear(date)
    await user.type(date, values.date)
  }
  await user.click(content)
  await user.type(content, values.content)
}
