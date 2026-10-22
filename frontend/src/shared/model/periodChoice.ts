import type { UpcomingPeriodKey, UpdatedPeriodKey, UpdatedPeriods } from './types'

/** 과거 기간 선택: ''(전체) / 프리셋 / 'custom'(직접 지정). */
export type PastPeriodChoice = '' | UpdatedPeriodKey | 'custom'
/** 기한 선택: 과거 선택에 향후 프리셋('next1m'/'next2m', 서버 upcoming 키 1m/2m)을 더한 것. */
export type DuePeriodChoice = PastPeriodChoice | 'next1m' | 'next2m'

export const PAST_PERIOD_LABELS: Record<UpdatedPeriodKey, string> = {
  '2w': '최근 2주',
  '1m': '최근 1개월',
  '2m': '최근 2개월',
  '3m': '최근 3개월',
  '6m': '최근 6개월',
}

export const UPCOMING_PERIOD_LABELS: Record<UpcomingPeriodKey, string> = { '1m': '향후 1개월', '2m': '향후 2개월' }

const UPCOMING_CHOICE: Record<'next1m' | 'next2m', UpcomingPeriodKey> = { next1m: '1m', next2m: '2m' }

/** 프리셋을 서버 날짜 범위로 푼다. ''·'custom'이거나 서버 응답에 그 키가 없으면 undefined. */
export function resolvePeriodChoice(choice: DuePeriodChoice, presets: UpdatedPeriods): { from: string; to: string } | undefined {
  if (choice === '' || choice === 'custom') return undefined
  const found =
    choice === 'next1m' || choice === 'next2m'
      ? presets.upcoming.find((p) => p.key === UPCOMING_CHOICE[choice])
      : presets.periods.find((p) => p.key === choice)
  return found ? { from: found.from, to: found.to } : undefined
}
