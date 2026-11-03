export interface WaterfallStep {
  from: number
  to: number
  kind: 'increase' | 'decrease' | 'total'
}

/** 폭포: 결과 순서대로 앞 누계에서 시작하는 뜬 막대. 빈 값은 0이고 0은 증가로 본다. `showTotal`이면 끝에 `[0, 최종 누계]` 합계 막대를 붙인다. */
export function waterfallSteps(values: readonly (number | null)[], showTotal: boolean): WaterfallStep[] {
  let running = 0
  const steps: WaterfallStep[] = values.map((raw) => {
    const value = raw ?? 0
    const from = running
    running += value
    return { from, to: running, kind: value >= 0 ? 'increase' : 'decrease' }
  })
  if (showTotal) steps.push({ from: 0, to: running, kind: 'total' })
  return steps
}
