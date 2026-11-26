import { canChangeReportVisibility, canDeleteReport, canEditReport, canViewReport } from '../../../shared/model/permissions'
import { compareIso } from '../../../shared/model/dates'
import type { ReportsGateway } from '../../../gateway/types'
import type {
  ReportChartInput,
  ReportIssue,
  ReportLayout,
  ReportQueryInput,
  ReportResult,
  ReportVisibility,
  SavedReport,
  SavedReportMeta,
  SavedReportSummary,
} from '../../../shared/model/reportTypes'
import {
  alreadyExists,
  forbidden,
  invalidReport,
  invalidState,
  notFound,
  SAVED_REPORT_CONFLICT_MESSAGE,
  SAVED_REPORT_DELETE_FORBIDDEN_MESSAGE,
  SAVED_REPORT_DUPLICATE_MESSAGE,
  SAVED_REPORT_NOT_FOUND_MESSAGE,
  SAVED_REPORT_VISIBILITY_FORBIDDEN_MESSAGE,
  validation,
} from '../errors'
import { REPORT_CATALOG } from '../seed/reportCatalog'
import type { SavedReportRequest } from '../store'
import { clone, read, requireUser, viewerOf, write, type MockContext } from './context'
import { userRef } from './views'

/**
 * 저장 리포트 Fake. 서버(`saved_report` 도메인·유스케이스)와 같은 규칙을 메모리에서 흉내 낸다.
 * - 권한은 `shared/model/permissions`의 같은 함수로 판정한다. 볼 수 없는 리포트는 없는 id와 같은 404 문구다.
 * - 판정 순서(덮어쓰기, 서버 RS-R12와 같다): 404 → 422(이름·설명·공개 범위·정의) → 403(수정) → 403(공개 범위) → 409(revision) → 409(이름 중복).
 * - 저장 정의를 읽을 수 없는 리포트(`definition`이 null, `brokenStoredReport`)는 목록에 남고 상세·실행·복제·배치 저장은 404 판정 뒤 422 stored-invalid, 새 정의로 덮어쓰면 복구된다(RS-R17).
 * - 이름은 모든 리포트 사이에서(만든 사람·공개 범위와 무관) 대소문자 무시로 고유하다. 만든 사람은 수정해도 바뀌지 않는다.
 * - 실행은 저장된 정의를 지금 카탈로그 규칙으로 다시 검사한 뒤 합성 결과를 돌려준다(설계 조회 기록 `reportQueries`에는 남지 않는다).
 */

const NAME_MAX = 100
const DESCRIPTION_MAX = 1000
const GENERATED_SQL = 'SELECT … /* fake saved */'
const VISIBILITIES: readonly string[] = ['public', 'private']
const VIEWS: readonly string[] = ['both', 'chart', 'table']
const ARRANGES: readonly string[] = ['side_by_side', 'stacked']
const TILES: readonly string[] = ['table', 'chart']

/** 서버의 기본 배치(표+차트, 표 → 차트, 두 줄). 저장된 배치가 없으면 이 값으로 열린다. */
export const DEFAULT_REPORT_LAYOUT: ReportLayout = { view: 'both', order: ['table', 'chart'], arrange: 'stacked' }

/** 서버 `parse_layout`과 같은 위치·코드: 값이 위반이면 `["layout", 항목]` 위반을 모두 모아 422(invalid-report). */
function checkLayout(layout: ReportLayout): ReportLayout {
  const raw = layout as unknown as { view: unknown; order: unknown; arrange: unknown }
  const issues: ReportIssue[] = []
  if (typeof raw.view !== 'string' || !VIEWS.includes(raw.view)) {
    issues.push({ location: ['layout', 'view'], code: 'invalid-value', message: '보기 방식은 both, chart, table 중 하나입니다' })
  }
  const order = raw.order
  const orderOk =
    Array.isArray(order) && order.length === 2 && order.every((t) => typeof t === 'string' && TILES.includes(t)) && order[0] !== order[1]
  if (!orderOk) issues.push({ location: ['layout', 'order'], code: 'invalid-value', message: '타일 순서는 table과 chart를 한 번씩 담아야 합니다' })
  if (typeof raw.arrange !== 'string' || !ARRANGES.includes(raw.arrange)) {
    issues.push({ location: ['layout', 'arrange'], code: 'invalid-value', message: '배치는 side_by_side 또는 stacked입니다' })
  }
  if (issues.length > 0) throw invalidReport(issues)
  return clone(layout)
}

/** 서버와 같은 문구·위치·code: 저장된 정의를 읽을 수 없는 리포트(RS-R17). */
export const STORED_INVALID_MESSAGE = '저장된 리포트 정의를 읽을 수 없습니다.'
const storedInvalid = () =>
  invalidReport([{ location: ['definition'], code: 'stored-invalid', message: STORED_INVALID_MESSAGE }])
/** 시드: 저장 정의를 읽을 수 없는 리포트는 `definition`이 null이다(서버 엔티티의 `definition = None`). */
const isBroken = (r: SavedReport): boolean => (r.definition as unknown) == null

type SavedMethods = Pick<ReportsGateway, 'list' | 'get' | 'create' | 'update' | 'copy' | 'remove' | 'run' | 'saveReportLayout'>

/** 조회 엔진(reports.ts)에서 받는 부분. 순환 import를 피하려고 인자로 받는다. */
export interface QueryEngine {
  issuesOf(input: ReportQueryInput): ReportIssue[]
  planQuery(ctx: MockContext, input: ReportQueryInput, record: boolean): { handler: ((i: ReportQueryInput) => ReportResult | Promise<ReportResult>) | null; result: ReportResult | null }
  settlePlan(plan: ReturnType<QueryEngine['planQuery']>, input: ReportQueryInput): Promise<ReportResult>
}

function normalizeMeta(meta: SavedReportMeta): SavedReportMeta {
  if (meta.name.includes('\0')) throw validation('리포트 이름에는 NUL 문자를 쓸 수 없습니다')
  const name = meta.name.trim()
  if (name === '') throw validation('리포트 이름을 입력하세요.')
  if ([...name].length > NAME_MAX) throw validation('리포트 이름은 100자 이내로 입력하세요.')
  if (meta.description.includes('\0')) throw validation('설명에는 NUL 문자를 쓸 수 없습니다')
  const description = meta.description.trim()
  if ([...description].length > DESCRIPTION_MAX) throw validation('설명은 1,000자 이내로 입력하세요.')
  if (!VISIBILITIES.includes(meta.visibility)) throw validation('공개 범위는 public 또는 private입니다.')
  return { name, description, visibility: meta.visibility as ReportVisibility }
}

/**
 * 차트 검증(서버 `parse_chart`의 일부만 흉내 낸다. 전체 규칙은 backend 단위 테스트가 정본, 명세 RC-R57).
 * - 그룹 컬럼이 3개 이상이면 종류와 무관하게(히스토그램 포함) `["chart"]` chart-too-many-groups 하나.
 * - 히스토그램이 아닌 종류는 그룹 컬럼이 없으면 `["chart"]` chart-needs-grouping, 범주가 그룹 컬럼의 index가 아니면 `["chart","category"]`.
 * - 통과한 차트는 서버처럼 정규화한다: 글자 앞뒤 공백 제거, 구간 생략은 auto, 히스토그램이 아니면 histogram null,
 *   폭포가 아니면 showTotal false, 콤보가 아니면 comboSeries null, 콤보 계열 생략은 옛 규칙(첫 값 막대·나머지 꺾은선),
 *   콤보의 secondaryAxis는 보조 축 계열이 하나라도 있는지로 계산한다.
 */
const AUTO_BINS = { binMode: 'auto', binCount: null, binWidth: null, overflow: null, underflow: null } as const

function normalizeChart(chart: ReportChartInput | null | undefined, definition: ReportQueryInput): ReportChartInput | null {
  if (chart === null || chart === undefined) return null
  const groups = definition.columns.map((c, i) => (c.group ? i : -1)).filter((i) => i >= 0)
  if (groups.length > 2) throw invalidReport([{ location: ['chart'], code: 'chart-too-many-groups', message: '차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다' }])
  if (chart.kind !== 'histogram') {
    if (groups.length === 0) throw invalidReport([{ location: ['chart'], code: 'chart-needs-grouping', message: '그룹핑한 결과로 차트를 만들 수 있습니다(히스토그램 제외)' }])
    if (typeof chart.category !== 'number' || !groups.includes(chart.category)) {
      throw invalidReport([{ location: ['chart', 'category'], code: 'chart-category-invalid', message: '범주 열은 그룹핑한 컬럼이어야 합니다' }])
    }
  }
  const comboSeries =
    chart.kind === 'combo'
      ? (chart.comboSeries ?? chart.values.map((_, i) => ({ type: i === 0 ? ('column' as const) : ('line' as const), secondary: i === 0 ? false : chart.secondaryAxis })))
      : null
  return {
    ...clone(chart),
    title: chart.title.trim(),
    categoryAxisTitle: chart.categoryAxisTitle.trim(),
    valueAxisTitle: chart.valueAxisTitle.trim(),
    histogram: chart.kind === 'histogram' ? clone(chart.histogram ?? AUTO_BINS) : null,
    showTotal: chart.kind === 'waterfall' ? chart.showTotal : false,
    comboSeries: comboSeries === null ? null : clone(comboSeries),
    secondaryAxis: comboSeries === null ? chart.secondaryAxis : comboSeries.some((series) => series.secondary),
  }
}

function entitiesOf(input: ReportQueryInput): SavedReportSummary['entities'] {
  const keys = [...input.columns.map((c) => c.field), ...input.conditions.map((c) => c.field)]
  const entities = new Set(REPORT_CATALOG.fields.filter((f) => keys.includes(f.key)).map((f) => f.entity))
  return REPORT_CATALOG.entities.map(({ key }) => key).filter((key) => key === 'deal' || entities.has(key))
}

export function createSavedReportsGateway(ctx: MockContext, engine: QueryEngine): SavedMethods {
  const state = () => ctx.store.reports
  const record = (entry: SavedReportRequest) => state().requests.push(clone(entry))

  /** 사용자 참조를 지금의 사용자 목록에서 다시 풀어 복사본을 돌려준다(퇴사 반영). */
  const view = (r: SavedReport): SavedReport => ({
    ...clone(r),
    owner: userRef(ctx.store.data, r.owner.id),
    updatedBy: userRef(ctx.store.data, r.updatedBy.id),
  })
  const summary = (r: SavedReport): SavedReportSummary => {
    const full = view(r)
    return {
      id: full.id,
      name: full.name,
      description: full.description,
      visibility: full.visibility,
      owner: full.owner,
      updatedBy: full.updatedBy,
      entities: full.entities,
      createdAt: full.createdAt,
      updatedAt: full.updatedAt,
      chartKind: full.chart?.kind ?? null,
    }
  }

  const visible = (id: number, viewer: ReturnType<typeof viewerOf>): SavedReport => {
    const found = state().saved.find((r) => r.id === id)
    if (!found || !canViewReport(viewer, found)) throw notFound(SAVED_REPORT_NOT_FOUND_MESSAGE)
    return found
  }
  const duplicated = (name: string, exceptId: number | null): boolean =>
    state().saved.some((r) => r.id !== exceptId && r.name.toLowerCase() === name.toLowerCase())
  /** 정의 위반이 있으면 그것만(차트는 검사하지 않음), 없으면 차트를 검사해 정규화한 값을 돌려준다. */
  const checkDefinition = (input: ReportQueryInput, chart: ReportChartInput | null | undefined = null): ReportChartInput | null => {
    const issues = engine.issuesOf(input)
    if (issues.length > 0) throw invalidReport(issues)
    return normalizeChart(chart, input)
  }
  const nextId = (): number => {
    const id = state().nextSavedId
    state().nextSavedId = id + 1
    return id
  }
  const insert = (
    ownerId: number,
    meta: SavedReportMeta,
    definition: ReportQueryInput,
    chart: ReportChartInput | null,
    layout: ReportLayout,
  ): SavedReport => {
    const now = ctx.clock.now()
    const owner = userRef(ctx.store.data, ownerId)
    const created: SavedReport = {
      id: nextId(),
      ...meta,
      owner,
      updatedBy: owner,
      entities: entitiesOf(definition),
      createdAt: now,
      updatedAt: now,
      revision: 1,
      definition: clone(definition),
      generatedSql: GENERATED_SQL,
      chart,
      chartProblem: null,
      layout,
    }
    state().saved.push(created)
    return view(created)
  }

  return {
    list: () =>
      read(ctx, () => {
        const viewer = viewerOf(requireUser(ctx))
        return state()
          .saved.filter((r) => canViewReport(viewer, r))
          .sort((a, b) => compareIso(b.updatedAt, a.updatedAt) || b.id - a.id)
          .map(summary)
      }),
    get: (id) =>
      read(ctx, () => {
        const viewer = viewerOf(requireUser(ctx))
        const found = visible(id, viewer)
        if (isBroken(found)) throw storedInvalid()
        return view(found)
      }),
    create: (input) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        record({ op: 'create', id: null, body: input })
        const meta = normalizeMeta(input)
        const chart = checkDefinition(input.definition, input.chart)
        const layout = input.layout ? checkLayout(input.layout) : clone(DEFAULT_REPORT_LAYOUT)
        if (duplicated(meta.name, null)) throw alreadyExists(SAVED_REPORT_DUPLICATE_MESSAGE)
        return insert(user.id, meta, input.definition, chart, layout)
      }),
    update: (id, input) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        const viewer = viewerOf(user)
        record({ op: 'update', id, body: input })
        const target = visible(id, viewer)
        const meta = normalizeMeta(input)
        const chart = checkDefinition(input.definition, input.chart)
        const layout = input.layout ? checkLayout(input.layout) : null
        if (!canEditReport(viewer, target)) throw forbidden('이 리포트를 수정할 권한이 없습니다.')
        if (meta.visibility !== target.visibility && !canChangeReportVisibility(viewer, target)) {
          throw forbidden(SAVED_REPORT_VISIBILITY_FORBIDDEN_MESSAGE)
        }
        if (input.revision !== target.revision) throw invalidState(SAVED_REPORT_CONFLICT_MESSAGE)
        if (duplicated(meta.name, target.id)) throw alreadyExists(SAVED_REPORT_DUPLICATE_MESSAGE)
        Object.assign(target, {
          ...meta,
          definition: clone(input.definition),
          entities: entitiesOf(input.definition),
          generatedSql: GENERATED_SQL,
          chart,
          chartProblem: null,
          // layout을 보내지 않으면 저장된 배치를 유지한다(차트와 달리 생략이 삭제가 아니다).
          ...(layout ? { layout } : {}),
          updatedBy: userRef(ctx.store.data, user.id),
          updatedAt: ctx.clock.now(),
          revision: target.revision + 1,
        })
        return view(target)
      }),
    copy: (id, metaInput) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        record({ op: 'copy', id, body: metaInput })
        const source = visible(id, viewerOf(user))
        if (isBroken(source)) throw storedInvalid()
        const meta = normalizeMeta(metaInput)
        const chart = checkDefinition(source.definition, source.chart)
        if (duplicated(meta.name, null)) throw alreadyExists(SAVED_REPORT_DUPLICATE_MESSAGE)
        return insert(user.id, meta, source.definition, chart, clone(source.layout ?? DEFAULT_REPORT_LAYOUT))
      }),
    saveReportLayout: async (id, body) => {
      const user = requireUser(ctx)
      record({ op: 'layout', id, body })
      const gate = state().layoutGate
      if (gate) {
        const attempt = state().requests.filter((r) => r.op === 'layout').length
        await gate({ id, attempt, body })
      }
      return write(ctx, () => {
        const viewer = viewerOf(user)
        const target = visible(id, viewer)
        if (isBroken(target)) throw storedInvalid()
        const layout = checkLayout(body.layout)
        if (!canEditReport(viewer, target)) throw forbidden('이 리포트를 수정할 권한이 없습니다.')
        if (body.revision !== target.revision) throw invalidState(SAVED_REPORT_CONFLICT_MESSAGE)
        Object.assign(target, {
          layout,
          updatedBy: userRef(ctx.store.data, user.id),
          updatedAt: ctx.clock.now(),
          revision: target.revision + 1,
        })
        return view(target)
      })
    },
    remove: (id) =>
      write(ctx, () => {
        const viewer = viewerOf(requireUser(ctx))
        record({ op: 'remove', id })
        const target = visible(id, viewer)
        if (!canDeleteReport(viewer, target)) throw forbidden(SAVED_REPORT_DELETE_FORBIDDEN_MESSAGE)
        state().saved = state().saved.filter((r) => r.id !== id)
      }),
    run: async (id) => {
      const loaded = await read(ctx, () => {
        const viewer = viewerOf(requireUser(ctx))
        record({ op: 'run', id })
        const found = visible(id, viewer)
        if (isBroken(found)) throw storedInvalid()
        const definition = clone(found.definition)
        return { definition, plan: engine.planQuery(ctx, definition, false) }
      })
      return engine.settlePlan(loaded.plan, loaded.definition)
    },
  }
}
