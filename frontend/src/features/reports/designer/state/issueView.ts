import type { AnchoredIssue } from './issues'
import type { InputIssue } from './toRequest'

/** 화면에 붙일 문구 한 건. `id`는 `aria-describedby`가 가리킨다. `part`는 입력 칸(없으면 항목 전체). */
export interface Message {
  id: string
  part: string | null
  text: string
}

const NONE: readonly Message[] = []

/** 위반 문구를 놓일 자리별로 모은 것(서버 위반 + 요청을 만들기 전 입력 문제). */
export interface IssueView {
  column(uid: number): readonly Message[]
  condition(uid: number): readonly Message[]
  columns: readonly Message[]
  conditions: readonly Message[]
  combine: readonly Message[]
  sort: readonly Message[]
  rowLimit: readonly Message[]
  /** 차트 설정 칸에 붙을 서버 위반(`part`는 칸 이름, 없으면 차트 전체). */
  chart: readonly Message[]
}

export const EMPTY_ISSUE_VIEW: IssueView = {
  column: () => NONE,
  condition: () => NONE,
  columns: NONE,
  conditions: NONE,
  combine: NONE,
  sort: NONE,
  rowLimit: NONE,
  chart: NONE,
}

export function buildIssueView(visible: readonly AnchoredIssue[], inputIssues: readonly InputIssue[], idPrefix: string): IssueView {
  let counter = 0
  const nextId = () => `${idPrefix}-issue-${(counter += 1)}`
  const byColumn = new Map<number, Message[]>()
  const byCondition = new Map<number, Message[]>()
  const loose = { columns: [] as Message[], conditions: [] as Message[], combine: [] as Message[], sort: [] as Message[], rowLimit: [] as Message[], chart: [] as Message[] }
  const push = (map: Map<number, Message[]>, uid: number, message: Message) => map.set(uid, [...(map.get(uid) ?? []), message])

  for (const { issue, target } of visible) {
    const text = issue.message
    switch (target.kind) {
      case 'column':
        push(byColumn, target.uid, { id: nextId(), part: target.part, text })
        break
      case 'condition':
        push(byCondition, target.uid, { id: nextId(), part: target.part, text })
        break
      case 'chart':
        loose.chart.push({ id: nextId(), part: target.part, text })
        break
      case 'general':
        break
      default:
        loose[target.kind].push({ id: nextId(), part: null, text })
    }
  }
  for (const input of inputIssues) push(input.part === 'prefix_length' ? byColumn : byCondition, input.uid, { id: nextId(), part: input.part, text: input.message })

  return {
    column: (uid) => byColumn.get(uid) ?? NONE,
    condition: (uid) => byCondition.get(uid) ?? NONE,
    ...loose,
  }
}

/** 입력 칸이 받을 접근성 속성: 그 칸(parts)의 문구가 있으면 invalid + describedby. */
export function describe(messages: readonly Message[], parts: readonly string[]): { 'aria-invalid'?: true; 'aria-describedby'?: string } {
  const ids = messages.filter((m) => m.part !== null && parts.includes(m.part)).map((m) => m.id)
  return ids.length > 0 ? { 'aria-invalid': true, 'aria-describedby': ids.join(' ') } : {}
}

export const idsOf = (messages: readonly Message[]): string | undefined => (messages.length > 0 ? messages.map((m) => m.id).join(' ') : undefined)
