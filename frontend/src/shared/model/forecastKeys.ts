import type { Code, ForecastColumn } from './types'

/** Forecast 다중 조건: URL `forecast` 값(콤마 구분)과 필터 버튼 요약. */

/** 서버 `app.web.schemas.deal.FORECAST_KEYS_MAX`와 같다. */
export const FORECAST_KEYS_MAX = 100
/** 서버 CodeKey 형식(소문자 시작, 소문자·숫자·'_', 50자 이내). 콤마가 들어갈 수 없어 URL 구분자로 쓴다. */
export const FORECAST_KEY_PATTERN = /^[a-z][a-z0-9_]{0,49}$/

/** URL `forecast` 값 → 정렬·중복 제거한 key 목록. 형식이 틀린 항목은 버리고, 서로 다른 key가 100개를 넘으면 [](서버 422 방지). */
export function parseForecastParam(raw: string | null): string[] {
  if (!raw) return []
  const found = new Set<string>()
  for (const part of raw.split(',')) {
    const key = part.trim()
    if (FORECAST_KEY_PATTERN.test(key)) found.add(key)
  }
  if (found.size > FORECAST_KEYS_MAX) return []
  return [...found].sort()
}

/** key 목록 → URL 값(알파벳순·중복 제거·콤마). 비면 ''. */
export function forecastParam(keys: Iterable<string>): string {
  return [...new Set(keys)].sort().join(',')
}

/** 한 key를 켜거나 끈 뒤의 URL 값. */
export function toggleForecastParam(raw: string | null, key: string, on: boolean): string {
  const current = parseForecastParam(raw)
  return forecastParam(on ? [...current, key] : current.filter((k) => k !== key))
}

function sameSet(selected: ReadonlySet<string>, keys: readonly string[]): boolean {
  return keys.length > 0 && keys.length === selected.size && keys.every((k) => selected.has(k))
}

/** 필터 버튼 요약. codes는 Forecast 코드 전체(Lost 포함, 아직 없으면 undefined). */
export function forecastSummary(selected: readonly string[], codes: readonly Code[] | undefined): string {
  if (selected.length === 0) return '전체'
  if (selected.length === 1) return codes?.find((c) => c.key === selected[0])?.name ?? selected[0]!
  if (codes) {
    const set = new Set(selected)
    const keys = (pick: (c: Code) => boolean) => codes.filter(pick).map((c) => c.key)
    if (sameSet(set, keys(() => true))) return '모두 선택'
    if (sameSet(set, keys((c) => c.outcome !== 'lost'))) return 'Lost 제외'
    if (sameSet(set, keys((c) => c.outcome === 'open'))) return 'Open 전체'
  }
  return `${selected.length}개 선택`
}

/** Dashboard Drill-down·Forecast 목록 링크에 싣는 Forecast 집합(정렬된 key). */
export interface ForecastSets {
  /** outcome이 open인 열. */
  open: readonly string[]
  /** outcome이 lost가 아닌 열(open + won). */
  notLost: readonly string[]
}

/** Dashboard 응답 `forecast.columns`(Lost 제외)로 만든다. 혹시 lost 열이 있어도 뺀다. */
export function forecastSetsOf(columns: readonly ForecastColumn[]): ForecastSets {
  const keys = (pick: (outcome: string) => boolean) => columns.filter((c) => pick(c.outcome)).map((c) => c.key).sort()
  return { open: keys((o) => o === 'open'), notLost: keys((o) => o !== 'lost') }
}
