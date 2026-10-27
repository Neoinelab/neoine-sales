/**
 * Reports 디자이너 화면 테스트 공용 도구(운영 코드에서 쓰지 않는다).
 * 화면 계약(접근 가능한 이름)은 계획 4.10과 `artifacts/20-agent-outputs/02-tests.md`의 표를 따른다.
 */

// App은 디자이너를 React.lazy로 불러오므로 청크 로딩이 findBy 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import '../features/reports/designer/ReportDesignerPage'
import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { afterEach, beforeEach, vi } from 'vitest'
import { mockControl, resetMock } from './fake/default'
import { renderAt, type RenderAtOptions } from './mockApp'
import { REPORT_CATALOG } from './fake/seed/reportCatalog'
import type { ReportQueryInput, ReportResult } from '../shared/model/reportTypes'

/** 테스트 기준 시각(서버 OS 오프셋 +09:00). */
export const REPORT_NOW = '2026-10-27T09:00:00+09:00'

/** describe 안에서 한 번 부른다: 시계를 고정하고 지정 응답·mock 스파이를 되돌린다. */
export function setupReportClock(): void {
  beforeEach(() => resetMock({ now: REPORT_NOW }))
  afterEach(() => {
    vi.restoreAllMocks()
    mockControl.setReportQueryHandler(null)
    resetMock({ now: null })
  })
}

type Rendered = Awaited<ReturnType<typeof renderAt>>
export type Designer = Rendered

/** 디자이너를 열고 필드 목록이 나올 때까지 기다린다. */
export async function openDesigner(options: RenderAtOptions = {}): Promise<Designer> {
  const rendered = await renderAt('/reports/new', options)
  await screen.findByRole('button', { name: 'Deal code 컬럼에 추가' })
  return rendered
}

export const fieldLabel = (key: string): string => {
  const found = REPORT_CATALOG.fields.find((f) => f.key === key)
  if (!found) throw new Error(`필드 없음: ${key}`)
  return found.label
}

/** 필드 이름(표시 이름)으로 컬럼에 추가한다. */
export async function addColumn(user: UserEvent, label: string): Promise<void> {
  await user.click(screen.getByRole('button', { name: `${label} 컬럼에 추가` }))
}

export async function addCondition(user: UserEvent, label: string): Promise<void> {
  await user.click(screen.getByRole('button', { name: `${label} 조건 추가` }))
}

export const chipList = (): HTMLElement => screen.getByRole('list', { name: '컬럼' })

/** n번째(0부터) 칩의 선택 버튼(aria-pressed가 있는 버튼). */
export function chipButton(index: number): HTMLElement {
  const item = chipItems()[index]
  const button = item?.querySelector<HTMLElement>('button[aria-pressed]')
  if (!button) throw new Error(`${index}번째 칩 없음`)
  return button
}

export function chipItems(): HTMLElement[] {
  const list = screen.queryByRole('list', { name: '컬럼' })
  return list ? within(list).queryAllByRole('listitem') : []
}

/** 칩 선택 버튼의 글자(배지 포함). */
export const chipTexts = (): string[] => chipItems().map((_, i) => chipButton(i).textContent ?? '')

export const settingsOf = (name: string): HTMLElement => screen.getByRole('region', { name: `컬럼 설정: ${name}` })

export const runButton = (): HTMLElement => screen.getByRole('button', { name: '조회' })

export async function runQuery(user: UserEvent): Promise<void> {
  await user.click(runButton())
}

export const resultTable = (): HTMLElement => screen.getByRole('table', { name: '조회 결과' })

/** 표의 본문 행(머리글 행 제외, 합계 행 포함)에서 셀 글자를 읽는다. */
export function tableTexts(): string[][] {
  return within(resultTable())
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell').map((c) => c.textContent ?? ''))
}

export function lastQuery(): ReportQueryInput {
  const queries = mockControl.reportQueries()
  const last = queries[queries.length - 1]
  if (!last) throw new Error('받은 조회 요청이 없습니다.')
  return last
}

/** 열 정의에 맞춘 결과를 돌려주는 핸들러를 건다. */
export function answerWith(result: ReportResult): void {
  mockControl.setReportQueryHandler(() => result)
}

/**
 * 디자이너를 열고(시드 복원이 지정 응답을 지우므로 그 뒤에) 응답을 정한 다음, 컬럼을 추가하고 조회해 결과 표까지 기다린다.
 * result가 null이면 Fake의 기본 규칙을 쓴다.
 */
export async function openAndRun(result: ReportResult | null, ...labels: string[]): Promise<Designer> {
  const rendered = await openDesigner()
  if (result) answerWith(result)
  for (const label of labels) await addColumn(rendered.user, label)
  await runQuery(rendered.user)
  await screen.findByRole('table', { name: '조회 결과' })
  return rendered
}
