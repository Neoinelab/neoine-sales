/**
 * Reports 4단계(차트) 화면 테스트 공용 도구(운영 코드에서 쓰지 않는다).
 *
 * 화면 계약(접근 가능한 이름, 테스트가 정한 것):
 * - 결과 카드: role=tablist 안에 tab "결과 표"·"차트"(aria-selected), 선택한 탭의 role=tabpanel.
 * - 차트 탭: 버튼 "차트 만들기"·"차트 삭제", 종류 버튼 10개(aria-pressed, 이름은 화면 이름), 그림은 role=img.
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
  resultColumn({ index, field: 'deal.amount', label: '금액(원)', type: 'number', valueType: 'integer', format: 'krw_thousand', aggregate: 'sum' })
export const usersCol = (index: number): ReportResultColumn =>
  resultColumn({ index, field: 'deal.users', label: 'Users', type: 'number', valueType: 'integer', format: 'thousands', aggregate: 'sum' })

/** Vendor 그룹 + 금액 + Users. 마지막 행의 Vendor는 비어 있다. */
export const ONE_GROUP_RESULT: ReportResult = resultOf({
  columns: [VENDOR_COL, amountCol(1), usersCol(2)],
  rows: [
    ['Silverfort', 3_000_000, 30],
    ['Okta', 1_500_000, 10],
    [null, 500_000, 5],
  ],
})

/** Vendor·Status 그룹 + 금액 + Users. Okta에는 Won 조합이 없다. */
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

/** 그룹 컬럼 1개(Vendor)·값 2개(금액, Users) 또는 그룹 2개(Vendor, Status)·값 2개로 설계하고 조회해 결과 표까지 기다린다. */
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
  await addColumn(user, '금액(원)')
  await addColumn(user, 'Users')
  answerWith(groups === 1 ? ONE_GROUP_RESULT : TWO_GROUP_RESULT)
  await runQuery(user)
  await screen.findByRole('table', { name: '조회 결과' })
  return rendered
}

export const tabNamed = (name: '결과 표' | '차트'): HTMLElement => screen.getByRole('tab', { name })

/** 차트 탭을 열고 안쪽이 나올 때까지 기다린다(lazy 청크). */
export async function openChartTab(user: UserEvent): Promise<void> {
  await user.click(tabNamed('차트'))
  await screen.findByRole('tabpanel')
}

/** 차트 탭에서 "차트 만들기"를 눌러 첫 차트가 그려질 때까지 기다린다. */
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
