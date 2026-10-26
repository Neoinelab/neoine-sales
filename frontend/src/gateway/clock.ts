import { formatWithOffset } from '../shared/model/dates'
import type { Clock, ServerTime } from './types'

const SERVER_NOW = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/

/** 서버 `now`의 오프셋(분). 오프셋이 없거나 시각으로 읽을 수 없으면 RangeError. */
function serverOffsetMinutes(now: string): number {
  const match = SERVER_NOW.exec(now)
  const zone = match?.[1]
  if (zone === undefined || Number.isNaN(Date.parse(now))) throw new RangeError(`서버 시각 형식이 올바르지 않습니다: ${now}`)
  if (zone === 'Z') return 0
  const minutes = Number(zone.slice(1, 3)) * 60 + Number(zone.slice(4, 6))
  return zone.startsWith('-') ? -minutes : minutes
}

/**
 * 서버 동기 시계. 브라우저 시계는 경과 시간 측정에만 쓰고, 지금과 오프셋은 서버가 알려 준 값을 따른다.
 * `Date.now`를 읽는 곳은 이 파일뿐이다(T-ARCH-03). 첫 동기 전 `now()`는 브라우저 시각이며 앱은 그 값을 화면에 쓰지 않는다.
 */
export function createServerClock(browserMs: () => number = Date.now): Clock {
  let skew = 0
  let offset: number | null = null
  return {
    now() {
      const ms = browserMs()
      return formatWithOffset(ms + skew, offset ?? -new Date(ms).getTimezoneOffset())
    },
    async syncWith(fetch): Promise<ServerTime> {
      const before = browserMs()
      const received = await fetch()
      const after = browserMs()
      const nextOffset = serverOffsetMinutes(received.now)
      // 서버 now는 요청과 응답의 중간 순간 값으로 본다(왕복 지연 절반 보정).
      skew = Date.parse(received.now) - (before + after) / 2
      offset = nextOffset
      return received
    },
  }
}
