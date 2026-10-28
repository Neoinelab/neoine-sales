/**
 * 저장 리포트 테스트 공용 도구(운영 코드에서 쓰지 않는다): 샘플 리포트 5건과 빌더.
 * 기본 로그인은 김영업(sales)이다. 5건의 관계는 다음과 같다.
 *
 * | id | 이름                | 만든 사람      | 공개 | 최종 수정자 | 수정 시각        | 데이터        |
 * | 11 | Vendor별 파이프라인   | 김영업         | O   | 김영업      | 2026-10-24 17:20 | Deal         |
 * | 12 | 내 비공개 점검        | 김영업         | X   | 김영업      | 2026-10-23 09:00 | Deal         |
 * | 13 | 박영업 공개 리포트    | 박영업         | O   | 김영업      | 2026-10-25 09:00 | Deal, Actions|
 * | 14 | 박영업 비공개        | 박영업         | X   | 박영업      | 2026-10-21 09:00 | Deal         |
 * | 15 | 퇴사자 공개 리포트    | 강퇴사(퇴사)   | O   | 강퇴사      | 2026-10-22 09:00 | Deal         |
 */

import type { ReportChartInput, ReportQueryInput, SavedReport } from '../shared/model/reportTypes'
import type { UserRef } from '../shared/model/types'
import { USER_ID } from './fake/seed/ids'

export const KIM: UserRef = { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' }
export const PARK: UserRef = { id: USER_ID.park, name: '박영업', role: 'sales', status: 'active' }
export const OLD: UserRef = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' }
export const ROOT: UserRef = { id: USER_ID.root, name: '최관리', role: 'admin', status: 'active' }

/** Vendor별 금액 합계, 금액 하한 조건, 합계 내림차순. 서버 규칙에 맞는 정의다. */
export const VENDOR_DEFINITION: ReportQueryInput = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum', label: '금액 합계' },
  ],
  conditions: [{ field: 'deal.amount', operator: 'gte', value: 1_500_000 }],
  combine: 'and',
  sort: { column: 1, direction: 'desc' },
  rowLimit: 1000,
}

/** Action 컬럼을 쓰는 정의(데이터 태그에 Actions가 붙는다). */
export const ACTION_DEFINITION: ReportQueryInput = {
  columns: [
    { field: 'deal.code', group: false },
    { field: 'action.action', group: false },
  ],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
}

/** 지금 카탈로그에 없는 필드를 쓰는 정의(저장 뒤 규칙이 바뀐 경우). */
export const BROKEN_DEFINITION: ReportQueryInput = {
  columns: [{ field: 'deal.nope', group: false }],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
}

export function savedReport(over: Partial<SavedReport> & { id: number }): SavedReport {
  const owner = over.owner ?? KIM
  return {
    name: `리포트 ${over.id}`,
    description: '',
    visibility: 'public',
    owner,
    updatedBy: owner,
    entities: ['deal'],
    createdAt: '2026-10-20T09:00:00+09:00',
    updatedAt: '2026-10-20T09:00:00+09:00',
    revision: 1,
    definition: VENDOR_DEFINITION,
    generatedSql: 'SELECT stored',
    chart: null,
    chartProblem: null,
    ...over,
  }
}

export const MINE_PUBLIC = savedReport({
  id: 11,
  name: 'Vendor별 파이프라인',
  description: 'Lost 제외, 올해 Expected Close',
  updatedAt: '2026-10-24T17:20:00+09:00',
})
export const MINE_PRIVATE = savedReport({ id: 12, name: '내 비공개 점검', visibility: 'private', updatedAt: '2026-10-23T09:00:00+09:00' })
export const PARK_PUBLIC = savedReport({
  id: 13,
  name: '박영업 공개 리포트',
  description: '박영업이 만들고 김영업이 고친 리포트',
  owner: PARK,
  updatedBy: KIM,
  entities: ['deal', 'action'],
  definition: ACTION_DEFINITION,
  updatedAt: '2026-10-25T09:00:00+09:00',
})
export const PARK_PRIVATE = savedReport({ id: 14, name: '박영업 비공개', visibility: 'private', owner: PARK, updatedAt: '2026-10-21T09:00:00+09:00' })
export const OLD_PUBLIC = savedReport({ id: 15, name: '퇴사자 공개 리포트', owner: OLD, updatedAt: '2026-10-22T09:00:00+09:00' })

export const SAVED_SAMPLES: SavedReport[] = [MINE_PUBLIC, MINE_PRIVATE, PARK_PUBLIC, PARK_PRIVATE, OLD_PUBLIC]

/** 목록 화면(김영업)에서 보이는 순서: 최종 수정 시각 내림차순. 박영업 비공개(14)는 보이지 않는다. */
export const KIM_LIST_ORDER = [PARK_PUBLIC, MINE_PUBLIC, MINE_PRIVATE, OLD_PUBLIC].map((r) => r.name)

/** VENDOR_DEFINITION(0: Vendor 그룹, 1: 금액 합계)에 맞는 세로 막대 차트 설정. */
export const VENDOR_CHART: ReportChartInput = {
  kind: 'bar',
  category: 0,
  series: null,
  values: [1],
  swap: false,
  title: 'Vendor별 금액',
  legend: 'top',
  dataLabels: false,
  categoryAxisTitle: 'Vendor',
  valueAxisTitle: '금액 합계',
  valueMin: null,
  valueMax: null,
  secondaryAxis: false,
}

/** 차트가 저장된 리포트(누적 막대 목록 표시용은 kind를 바꿔 쓴다). */
export const WITH_CHART = savedReport({ id: 21, name: '차트 있는 리포트', chart: VENDOR_CHART, updatedAt: '2026-10-26T09:00:00+09:00' })

/** 저장 대화상자 입력의 기본 모양. */
export function reportInput(over: Partial<{ name: string; description: string; visibility: 'public' | 'private'; chart: ReportChartInput | null }> = {}) {
  return { name: '새 리포트 이름', description: '', visibility: 'public' as const, definition: VENDOR_DEFINITION, chart: null as ReportChartInput | null, ...over }
}

/** 어디에도 없는 리포트 id(서버 허용 범위 1~2^53−1 안의 최댓값). */
export const NO_REPORT_ID = Number.MAX_SAFE_INTEGER
