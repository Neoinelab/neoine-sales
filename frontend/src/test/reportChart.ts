/**
 * Reports 4단계(차트) 화면 테스트 공용 도구(운영 코드에서 쓰지 않는다).
 *
 * 화면 계약(접근 가능한 이름, 테스트가 정한 것):
 * - 디자이너는 "작성"·"결과" 탭이고 차트는 결과 탭의 "차트 타일"(role=region)에 있다(결과 표 타일과 나란히). 배치 계약은 `reportLayout.ts`.
 * - 차트 타일: 빈 상태에 버튼 "차트 만들기", 차트가 있으면 머리에 버튼 "차트 설정"(aria-expanded)이 있어 설정 패널을 열고 닫는다
 *   (기본은 닫힘, "차트 만들기"로 만들면 열림). 패널 안에 버튼 "차트 삭제", 종류 버튼 10개(aria-pressed, 이름은 화면 이름). 그림은 role=img.
 * - 설정 칸(getByLabelText): "범주"(select), "계열"(select), "값"(그룹 안에 값 열마다 checkbox), "행/열 전환", "차트 제목",
 *   "범례"(select: 위·오른쪽·아래·숨김), "데이터 레이블", "가로축 제목", "세로축 제목", "세로축 최소", "세로축 최대", "보조 축".
 * - 안내 문구는 계획 AC11·AC17·AC19·AC20의 글자 그대로.
 */

import { screen, within } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'
import { expect } from 'vitest'
import { columnHeader } from '../features/reports/designer/format/formatCell'
import type { ReportResult, ReportResultColumn } from '../shared/model/reportTypes'
import { lastChart } from './chartMock'
import { resultColumn, resultOf } from './reportDesigner'
import { addColumn, answerWith, chipButton, openDesigner, runQuery, settingsOf, type Designer } from './reportScreen'

// 차트 탭은 React.lazy 청크이므로 첫 로딩이 findBy 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import '../features/reports/chart/ChartTab'

export const VENDOR_COL = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
export const STATUS_COL = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
export const amountCol = (index: number): ReportResultColumn =>
  resultColumn({ index, field: 'deal.amount', label: '금액', type: 'number', valueType: 'integer', format: null, unit: 'krw_thousand', aggregate: 'sum' })
export const usersCol = (index: number): ReportResultColumn =>
  resultColumn({ index, field: 'deal.users', label: 'Users count', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum' })

/** Vendor 그룹 + 금액 + Users count. 마지막 행의 Vendor는 비어 있다. */
export const ONE_GROUP_RESULT: ReportResult = resultOf({
  columns: [VENDOR_COL, amountCol(1), usersCol(2)],
  rows: [
    ['Silverfort', 3_000_000, 30],
    ['Okta', 1_500_000, 10],
    [null, 500_000, 5],
  ],
})

/** Vendor·Status 그룹 + 금액 + Users count. Okta에는 Won 조합이 없다. */
export const TWO_GROUP_RESULT: ReportResult = resultOf({
  columns: [VENDOR_COL, STATUS_COL, amountCol(2), usersCol(3)],
  rows: [
    ['Silverfort', 'Won', 3_000_000, 30],
    ['Silverfort', 'Open', 1_000_000, 10],
    ['Okta', 'Open', 2_000_000, 20],
  ],
})

export const AMOUNT_HEADER = columnHeader(amountCol(1))
export const USERS_HEADER = columnHeader(usersCol(2))

/** 그룹 컬럼 1개(Vendor)·값 2개(금액, Users count) 또는 그룹 2개(Vendor, Status)·값 2개로 설계하고 조회해 결과 표까지 기다린다. */
export async function openGroupedDesigner(groups: 1 | 2): Promise<Designer> {
  const rendered = await openDesigner()
  const { user } = rendered
  await addColumn(user, 'Vendor')
  await user.click(chipButton(0))
  await user.click(within(settingsOf('Vendor')).getByRole('checkbox', { name: '그룹핑' }))
  if (groups === 2) {
    await addColumn(user, 'Status')
    await user.click(chipButton(1))
    await user.click(within(settingsOf('Status')).getByRole('checkbox', { name: '그룹핑' }))
  }
  await addColumn(user, '금액')
  await addColumn(user, 'Users count')
  answerWith(groups === 1 ? ONE_GROUP_RESULT : TWO_GROUP_RESULT)
  await runQuery(user)
  await screen.findByRole('table', { name: '조회 결과' })
  return rendered
}

/** 차트 타일 머리의 '차트 설정' 버튼(차트가 있을 때만 있다). */
export const chartToggle = (): HTMLElement | null => screen.queryByRole('button', { name: '차트 설정' })

/**
 * 결과 탭의 차트 타일을 보이게 하고(결과 탭으로 이동, lazy 청크가 나올 때까지 기다림) 설정 패널이 닫혀 있으면 연다.
 * 차트가 없는 빈 상태에는 설정 버튼이 없으므로 열 것이 없다.
 */
export async function openChartTab(user: UserEvent): Promise<void> {
  await user.click(screen.getByRole('tab', { name: /^결과/ }))
  await screen.findByRole('region', { name: '차트 타일' })
  const toggle = chartToggle()
  if (!toggle) return
  if (toggle.getAttribute('aria-expanded') === 'false') await user.click(toggle)
  await screen.findByRole('button', { name: '차트 삭제' }) // 설정 패널은 차트 청크 안에 있다
}

/** 차트 타일에서 "차트 만들기"를 눌러 첫 차트가 그려질 때까지 기다린다(설정 패널이 열린다). */
export async function createChart(user: UserEvent): Promise<void> {
  await user.click(await screen.findByRole('button', { name: '차트 만들기' }))
  await screen.findByRole('img')
}

export const kindButton = (name: string): HTMLElement => screen.getByRole('button', { name })
export const panelField = (label: string): HTMLElement => screen.getByLabelText(label)

/** 마지막으로 그려진 차트의 옵션 중 경로의 값. */
export function optionAt(...path: (string | number)[]): unknown {
  let current: unknown = lastChart().options
  for (const key of path) {
    if (typeof current !== 'object' || current === null) return undefined
    current = (current as Record<string | number, unknown>)[key]
  }
  return current
}

export const chartLabels = (): unknown => lastChart().data.labels
export const chartDatasets = (): { label?: string; data: unknown[] }[] => lastChart().data.datasets as unknown as { label?: string; data: unknown[] }[]

/** 값 체크박스 묶음. */
export const valueGroup = (): HTMLElement => screen.getByRole('group', { name: '값' })

export function expectPressed(name: string): void {
  expect(screen.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true')
}
