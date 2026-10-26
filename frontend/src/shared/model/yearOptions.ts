/**
 * 연도 선택지: min(earliestYear, 올해) ~ 올해+1 연속(오름차순). Deals 목록·Dashboard·Forecast 공통.
 * earliestYear를 모르면(로딩·오류·Deal 없음) 올해·내년. 범위 밖 current(URL 연도)는 더해서 화면과 조회 조건을 맞춘다.
 */
export function selectableYears(thisYear: number, earliestYear: number | null | undefined, current?: number): number[] {
  const start = Math.min(earliestYear ?? thisYear, thisYear)
  const years: number[] = []
  for (let y = start; y <= thisYear + 1; y += 1) years.push(y)
  if (current !== undefined && Number.isInteger(current) && !years.includes(current)) {
    years.push(current)
    years.sort((a, b) => a - b)
  }
  return years
}
