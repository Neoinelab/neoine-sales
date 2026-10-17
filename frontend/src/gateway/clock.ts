import { formatWithOffset } from '../shared/model/dates'
import type { Clock } from './types'

/** 브라우저(OS) 로컬 시각. 오프셋 포함 ISO(예: 2026-10-17T09:00:00+09:00). */
export const systemClock: Clock = {
  now: () => formatWithOffset(Date.now(), -new Date().getTimezoneOffset()),
}
