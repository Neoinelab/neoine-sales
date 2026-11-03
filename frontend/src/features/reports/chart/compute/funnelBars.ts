export interface FunnelBar {
  /** 입력에서의 원래 위치. */
  index: number
  value: number
  /** 가운데 정렬 막대 `[-v/2, v/2]`. */
  range: [number, number]
}

/** 깔때기: 0 이하·빈 값을 빼고 결과 순서대로 가운데 정렬 막대를 만든다. */
export function funnelBars(values: readonly (number | null)[]): { bars: FunnelBar[]; skipped: number } {
  const bars: FunnelBar[] = []
  values.forEach((value, index) => {
    if (value !== null && value > 0) bars.push({ index, value, range: [-value / 2, value / 2] })
  })
  return { bars, skipped: values.length - bars.length }
}
