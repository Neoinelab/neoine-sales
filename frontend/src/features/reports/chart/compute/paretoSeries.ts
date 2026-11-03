/** 파레토: 0 이하·빈 값 항목을 빼고 값 내림차순(같으면 결과 순서 유지)으로 정렬하고 누적 %를 구한다. */
export interface ParetoSeries {
  labels: string[]
  values: number[]
  /** 누계 / 합계 × 100(%). 마지막은 정확히 100이다. */
  cumulative: number[]
  /** 입력에서의 원래 위치(툴팁에서 원래 칸을 찾는 데 쓴다). */
  indices: number[]
  /** 뺀 항목 수. */
  skipped: number
}

export function paretoSeries(labels: readonly string[], values: readonly (number | null)[]): ParetoSeries {
  const items = values
    .map((value, index) => ({ value, index }))
    .filter((item): item is { value: number; index: number } => item.value !== null && item.value > 0)
    .sort((a, b) => b.value - a.value || a.index - b.index)
  const total = items.reduce((sum, item) => sum + item.value, 0)
  let running = 0
  const cumulative = items.map((item, i) => {
    running += item.value
    return i === items.length - 1 ? 100 : (running * 100) / total
  })
  return {
    labels: items.map((item) => labels[item.index] ?? ''),
    values: items.map((item) => item.value),
    cumulative,
    indices: items.map((item) => item.index),
    skipped: values.length - items.length,
  }
}
