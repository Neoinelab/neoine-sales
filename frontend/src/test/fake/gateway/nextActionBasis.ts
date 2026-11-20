/** Fake 전용: 서버 RK-R1과 같은 Next Action 기준 행 선택. 앱 코드(`shared/model`)에는 이 계산이 없다. */

export interface BasisCandidate {
  id: number
  actedOn: string
  nextAction: string | null
  dueDate: string | null
  nextActionStatus: string | null
}

/**
 * ① 지난 Open Next Action 행(Open이고 Due < 오늘)이 있으면 Due가 가장 이른 행(같으면 id가 큰 행, 수행일은 보지 않음).
 * ② 없으면 Next Action이 있는 행 중 수행일 내림차순·id 내림차순 첫 행(상태는 보지 않음).
 * `today`는 'YYYY-MM-DD' 업무 날짜다. 입력 배열은 바꾸지 않는다.
 */
export function pickNextActionBasis<T extends BasisCandidate>(rows: readonly T[], today: string): T | null {
  const withNext = rows.filter((r) => r.nextAction !== null)
  let overdue: T | null = null
  for (const r of withNext) {
    if (r.nextActionStatus !== 'open' || r.dueDate === null || r.dueDate >= today) continue
    const od = overdue?.dueDate ?? ''
    if (overdue === null || r.dueDate < od || (r.dueDate === od && r.id > overdue.id)) overdue = r
  }
  if (overdue !== null) return overdue
  let latest: T | null = null
  for (const r of withNext) {
    if (latest === null || r.actedOn > latest.actedOn || (r.actedOn === latest.actedOn && r.id > latest.id)) latest = r
  }
  return latest
}
