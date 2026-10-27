import type { ReportIssue } from '../../../../shared/model/reportTypes'

/** 마지막 조회 때 요청 index → 화면 uid 대응. */
export interface RunUids {
  columnUids: readonly number[]
  conditionUids: readonly number[]
}

export type IssueTarget =
  | { kind: 'column'; uid: number; part: string | null }
  | { kind: 'condition'; uid: number; part: string | null }
  | { kind: 'columns' }
  | { kind: 'conditions' }
  | { kind: 'combine' }
  | { kind: 'sort' }
  | { kind: 'rowLimit' }
  | { kind: 'chart'; part: string | null }
  | { kind: 'general' }

export interface AnchoredIssue {
  issue: ReportIssue
  target: IssueTarget
}

const GENERAL: IssueTarget = { kind: 'general' }

function itemTarget(kind: 'column' | 'condition', uids: readonly number[], location: ReportIssue['location']): IssueTarget {
  const index = location[1]
  if (typeof index !== 'number') return GENERAL
  const uid = uids[index]
  if (uid === undefined) return GENERAL
  const part = location[2]
  return { kind, uid, part: typeof part === 'string' ? part : null }
}

function targetOf(location: ReportIssue['location'], run: RunUids): IssueTarget {
  switch (location[0]) {
    case 'columns':
      return location.length === 1 ? { kind: 'columns' } : itemTarget('column', run.columnUids, location)
    case 'conditions':
      return location.length === 1 ? { kind: 'conditions' } : itemTarget('condition', run.conditionUids, location)
    case 'combine':
      return { kind: 'combine' }
    case 'sort':
      return { kind: 'sort' }
    case 'row_limit':
      return { kind: 'rowLimit' }
    case 'chart': {
      const part = location[1]
      return { kind: 'chart', part: typeof part === 'string' ? part : null }
    }
    default:
      return GENERAL
  }
}

/** 서버 위반 위치를 마지막 조회의 컬럼·조건 uid로 옮긴다. 모르는 위치는 요약에만 보인다(general). */
export function issueAnchors(issues: readonly ReportIssue[], run: RunUids): AnchoredIssue[] {
  return issues.map((issue) => ({ issue, target: targetOf(issue.location, run) }))
}

/** 지금 화면에 보일 위반: 지워진 컬럼·조건의 위반과 수정한(`dismissedUids`) 항목의 위반은 뺀다. */
export function visibleIssues(anchored: readonly AnchoredIssue[], live: RunUids, dismissedUids: ReadonlySet<number>): AnchoredIssue[] {
  return anchored.filter(({ target }) => {
    if (target.kind === 'column') return live.columnUids.includes(target.uid) && !dismissedUids.has(target.uid)
    if (target.kind === 'condition') return live.conditionUids.includes(target.uid) && !dismissedUids.has(target.uid)
    return true
  })
}
