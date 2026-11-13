import type { DealAction } from './types'

/**
 * Deal의 Next Action 기준 행: Next Action이 있는 가장 최근 Action(수행일 내림차순, 같으면 id 내림차순).
 * 서버(`deal_derived.py`)와 같은 규칙이다. 입력 배열은 바꾸지 않는다.
 */
export function latestWithNextAction(actions: readonly DealAction[]): DealAction | null {
  let best: DealAction | null = null
  for (const a of actions) {
    if (a.nextAction === null) continue
    if (best === null) {
      best = a
      continue
    }
    if (a.actedOn > best.actedOn || (a.actedOn === best.actedOn && a.id > best.id)) best = a
  }
  return best
}
