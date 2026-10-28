import { useCallback, useId, useRef, useState } from 'react'
import { reportRunFailure, useRunReport } from '../../../data/reports'
import type { ReportCatalog, ReportIssue, ReportResult, ReportRunFailure } from '../../../shared/model/reportTypes'
import { columnName } from './names'
import type { SummaryItem } from './ResultCard'
import { fieldByKey } from './state/columnRules'
import { sameDesign, type DesignerAction, type DesignerState } from './state/designerState'
import { buildIssueView, EMPTY_ISSUE_VIEW, type IssueView } from './state/issueView'
import { issueAnchors, visibleIssues, type AnchoredIssue, type IssueTarget } from './state/issues'
import { toReportRequest, type InputIssue } from './state/toRequest'

/** 마지막으로 보낸 조회: 요청 index → uid 대응(위반 위치 매핑)과 그때의 설계, 결과 또는 실패. */
interface LastRun {
  id: number
  columnUids: number[]
  conditionUids: number[]
  requestState: DesignerState
  result?: ReportResult
  failure?: ReportRunFailure
}

/** 사용자가 고친 항목의 위반 표시를 지우기 위한 기록(uid는 컬럼·조건, kinds는 결합·정렬·최대 행 같은 항목). */
interface Dismissed {
  uids: ReadonlySet<number>
  kinds: ReadonlySet<IssueTarget['kind']>
}

const NO_UIDS: readonly number[] = []
const NOTHING: Dismissed = { uids: new Set(), kinds: new Set() }

function addUid(prev: Dismissed, uid: number): Dismissed {
  return prev.uids.has(uid) ? prev : { ...prev, uids: new Set(prev.uids).add(uid) }
}

function addKind(prev: Dismissed, kind: IssueTarget['kind']): Dismissed {
  return prev.kinds.has(kind) ? prev : { ...prev, kinds: new Set(prev.kinds).add(kind) }
}

/** 어떤 편집이 어떤 위반 표시를 지우는지. 옮기기·선택은 지우지 않는다. */
function dismissFor(prev: Dismissed, action: DesignerAction): Dismissed {
  switch (action.type) {
    case 'updateColumn':
    case 'changeConditionField':
    case 'changeOperator':
    case 'changeDraft':
      return addUid(prev, action.uid)
    case 'addColumn':
    case 'removeColumn':
      return addKind(prev, 'columns')
    case 'addCondition':
    case 'removeCondition':
      return addKind(prev, 'conditions')
    case 'setCombine':
      return addKind(prev, 'combine')
    case 'setSort':
      return addKind(prev, 'sort')
    case 'setRowLimit':
      return addKind(prev, 'rowLimit')
    case 'createChart':
    case 'changeChart':
    case 'setChartKind':
    case 'removeChart':
      return addKind(prev, 'chart')
    default:
      return prev
  }
}

function whereOf(target: IssueTarget, state: DesignerState, catalog: ReportCatalog): string | null {
  switch (target.kind) {
    case 'column': {
      const index = state.columns.findIndex((c) => c.uid === target.uid)
      const column = state.columns[index]
      return column ? `컬럼 ${index + 1}(${columnName(column, catalog)})` : null
    }
    case 'condition': {
      const index = state.conditions.findIndex((c) => c.uid === target.uid)
      const condition = state.conditions[index]
      return condition ? `조건 ${index + 1}(${fieldByKey(catalog, condition.field)?.label ?? condition.field})` : null
    }
    case 'columns':
      return '컬럼'
    case 'conditions':
      return '조건'
    case 'combine':
      return '조건 결합'
    case 'sort':
      return '정렬'
    case 'rowLimit':
      return '최대 행'
    case 'chart':
      return '차트'
    default:
      return null
  }
}

export interface DesignerRun {
  run: () => Promise<void>
  running: boolean
  /** 설계 편집을 알려 해당 위반 표시를 지운다. */
  noteEdit: (action: DesignerAction) => void
  /** 조회 기록·위반 표시를 모두 지운다(초기화). */
  clear: () => void
  /** 요청을 만들 수 없는 입력 문제를 조회 때와 같은 방식으로 보인다(저장 흐름용). */
  showInputIssues: (issues: InputIssue[]) => void
  /** 저장 요청이 정의 위반(422)이면 조회 실패와 같은 방식으로 위반을 보인다(결과는 그대로 둔다). */
  showSaveIssues: (message: string, issues: ReportIssue[]) => void
  result: ReportResult | null
  failure: ReportRunFailure | null
  stale: boolean
  /** 조회마다 바뀌는 번호. 결과 화면 상태(페이지·합계 행)를 새 결과에서 처음으로 되돌리는 key로 쓴다. */
  runId: number
  /** 마지막으로 보낸 조회의 열 i번째 uid(차트의 참조를 결과 열로 옮기는 데 쓴다). 조회한 적이 없으면 빈 배열. */
  resultColumnUids: readonly number[]
  issues: IssueView
  summary: SummaryItem[]
}

/** 조회 실행과 결과·실패·위반 표시 상태. 화면은 이 훅의 값만 그린다. */
export function useDesignerRun(state: DesignerState, catalog: ReportCatalog, seed: ReportResult | null = null): DesignerRun {
  const mutation = useRunReport()
  const idPrefix = useId()
  const seq = useRef(seed ? 1 : 0)
  // 저장 직후 이어 받은 결과가 있으면 그 설계로 이미 조회한 것으로 둔다.
  const [lastRun, setLastRun] = useState<LastRun | null>(() =>
    seed ? { id: 1, columnUids: state.columns.map((c) => c.uid), conditionUids: state.conditions.map((c) => c.uid), requestState: state, result: seed } : null,
  )
  const [inputIssues, setInputIssues] = useState<InputIssue[]>([])
  const [dismissed, setDismissed] = useState<Dismissed>(NOTHING)

  const run = async () => {
    setDismissed(NOTHING)
    const built = toReportRequest(state, catalog)
    if ('inputIssues' in built) {
      setInputIssues(built.inputIssues)
      return
    }
    setInputIssues([])
    // 새 조회를 시작하면 이전 실패 표시는 걷는다(이전 결과는 응답이 올 때까지 남긴다).
    setLastRun((prev) => (prev?.failure ? null : prev))
    const base = { id: (seq.current += 1), columnUids: built.columnUids, conditionUids: built.conditionUids, requestState: state }
    try {
      setLastRun({ ...base, result: await mutation.mutateAsync(built.request) })
    } catch (error) {
      setLastRun({ ...base, failure: reportRunFailure(error) })
    }
  }

  const noteEdit = useCallback((action: DesignerAction) => setDismissed((prev) => dismissFor(prev, action)), [])
  const showSaveIssues = (message: string, issues: ReportIssue[]) => {
    setDismissed(NOTHING)
    setLastRun((prev) => ({
      id: prev?.id ?? (seq.current += 1),
      columnUids: state.columns.map((c) => c.uid),
      conditionUids: state.conditions.map((c) => c.uid),
      requestState: state,
      ...(prev?.result ? { result: prev.result } : {}),
      failure: { kind: 'invalid', message, issues },
    }))
  }
  const clear = useCallback(() => {
    setLastRun(null)
    setInputIssues([])
    setDismissed(NOTHING)
  }, [])

  const live = { columnUids: state.columns.map((c) => c.uid), conditionUids: state.conditions.map((c) => c.uid) }
  const failure = lastRun?.failure ?? null
  const anchored: AnchoredIssue[] = failure?.kind === 'invalid' && lastRun ? issueAnchors(failure.issues, lastRun) : []
  const visible = visibleIssues(anchored, live, dismissed.uids).filter((a) => !dismissed.kinds.has(a.target.kind))
  const shownInput = inputIssues.filter((i) => (live.conditionUids.includes(i.uid) || live.columnUids.includes(i.uid)) && !dismissed.uids.has(i.uid))
  const issues = visible.length > 0 || shownInput.length > 0 ? buildIssueView(visible, shownInput, idPrefix) : EMPTY_ISSUE_VIEW

  return {
    run,
    running: mutation.isPending,
    noteEdit,
    clear,
    showSaveIssues,
    showInputIssues: (list) => {
      setDismissed(NOTHING)
      setInputIssues(list)
    },
    result: lastRun?.result ?? null,
    failure,
    runId: lastRun?.id ?? 0,
    resultColumnUids: lastRun?.columnUids ?? NO_UIDS,
    stale: lastRun?.result !== undefined && !sameDesign(state, lastRun.requestState),
    issues,
    summary: visible.map(({ issue, target }, i) => ({ key: `${i}`, where: whereOf(target, state, catalog), message: issue.message })),
  }
}
