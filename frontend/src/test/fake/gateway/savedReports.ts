import { canChangeReportVisibility, canDeleteReport, canEditReport, canViewReport } from '../../../shared/model/permissions'
import { compareIso } from '../../../shared/model/dates'
import type { ReportsGateway } from '../../../gateway/types'
import type {
  ReportIssue,
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
 * - 판정 순서: 404 → 422(이름·설명·공개 범위·정의) → 403(수정) → 409(revision) → 403(공개 범위) → 409(이름 중복).
 * - 이름은 모든 리포트 사이에서(만든 사람·공개 범위와 무관) 대소문자 무시로 고유하다. 만든 사람은 수정해도 바뀌지 않는다.
 * - 실행은 저장된 정의를 지금 카탈로그 규칙으로 다시 검사한 뒤 합성 결과를 돌려준다(설계 조회 기록 `reportQueries`에는 남지 않는다).
 */

const NAME_MAX = 100
const DESCRIPTION_MAX = 1000
const GENERATED_SQL = 'SELECT … /* fake saved */'
const VISIBILITIES: readonly string[] = ['public', 'private']

type SavedMethods = Pick<ReportsGateway, 'list' | 'get' | 'create' | 'update' | 'copy' | 'remove' | 'run'>

/** 조회 엔진(reports.ts)에서 받는 부분. 순환 import를 피하려고 인자로 받는다. */
export interface QueryEngine {
  issuesOf(input: ReportQueryInput): ReportIssue[]
  planQuery(ctx: MockContext, input: ReportQueryInput, record: boolean): { handler: ((i: ReportQueryInput) => ReportResult | Promise<ReportResult>) | null; result: ReportResult | null }
  settlePlan(plan: ReturnType<QueryEngine['planQuery']>, input: ReportQueryInput): Promise<ReportResult>
}

function normalizeMeta(meta: SavedReportMeta): SavedReportMeta {
  const name = meta.name.trim()
  if (name === '' || name.includes('\0')) throw validation('리포트 이름을 입력하세요.')
  if ([...name].length > NAME_MAX) throw validation('리포트 이름은 100자 이내로 입력하세요.')
  const description = meta.description.trim()
  if (description.includes('\0') || [...description].length > DESCRIPTION_MAX) throw validation('설명은 1,000자 이내로 입력하세요.')
  if (!VISIBILITIES.includes(meta.visibility)) throw validation('공개 범위는 public 또는 private입니다.')
  return { name, description, visibility: meta.visibility as ReportVisibility }
}

function entitiesOf(input: ReportQueryInput): SavedReportSummary['entities'] {
  const keys = [...input.columns.map((c) => c.field), ...input.conditions.map((c) => c.field)]
  const hasAction = keys.some((key) => REPORT_CATALOG.fields.find((f) => f.key === key)?.entity === 'action')
  return hasAction ? ['deal', 'action'] : ['deal']
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
    }
  }

  const visible = (id: number, viewer: ReturnType<typeof viewerOf>): SavedReport => {
    const found = state().saved.find((r) => r.id === id)
    if (!found || !canViewReport(viewer, found)) throw notFound(SAVED_REPORT_NOT_FOUND_MESSAGE)
    return found
  }
  const duplicated = (name: string, exceptId: number | null): boolean =>
    state().saved.some((r) => r.id !== exceptId && r.name.toLowerCase() === name.toLowerCase())
  const checkDefinition = (input: ReportQueryInput): void => {
    const issues = engine.issuesOf(input)
    if (issues.length > 0) throw invalidReport(issues)
  }
  const nextId = (): number => {
    const id = state().nextSavedId
    state().nextSavedId = id + 1
    return id
  }
  const insert = (ownerId: number, meta: SavedReportMeta, definition: ReportQueryInput): SavedReport => {
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
        return view(visible(id, viewer))
      }),
    create: (input) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        record({ op: 'create', id: null, body: input })
        const meta = normalizeMeta(input)
        checkDefinition(input.definition)
        if (duplicated(meta.name, null)) throw alreadyExists(SAVED_REPORT_DUPLICATE_MESSAGE)
        return insert(user.id, meta, input.definition)
      }),
    update: (id, input) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        const viewer = viewerOf(user)
        record({ op: 'update', id, body: input })
        const target = visible(id, viewer)
        const meta = normalizeMeta(input)
        checkDefinition(input.definition)
        if (!canEditReport(viewer, target)) throw forbidden('이 리포트를 수정할 권한이 없습니다.')
        if (input.revision !== target.revision) throw invalidState(SAVED_REPORT_CONFLICT_MESSAGE)
        if (meta.visibility !== target.visibility && !canChangeReportVisibility(viewer, target)) {
          throw forbidden(SAVED_REPORT_VISIBILITY_FORBIDDEN_MESSAGE)
        }
        if (duplicated(meta.name, target.id)) throw alreadyExists(SAVED_REPORT_DUPLICATE_MESSAGE)
        Object.assign(target, {
          ...meta,
          definition: clone(input.definition),
          entities: entitiesOf(input.definition),
          generatedSql: GENERATED_SQL,
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
        const meta = normalizeMeta(metaInput)
        checkDefinition(source.definition)
        if (duplicated(meta.name, null)) throw alreadyExists(SAVED_REPORT_DUPLICATE_MESSAGE)
        return insert(user.id, meta, source.definition)
      }),
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
        const definition = clone(visible(id, viewer).definition)
        return { definition, plan: engine.planQuery(ctx, definition, false) }
      })
      return engine.settlePlan(loaded.plan, loaded.definition)
    },
  }
}
