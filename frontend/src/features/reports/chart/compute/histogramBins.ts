import type { ReportHistogramBins } from '../../../../shared/model/reportTypes'

/** 구간 하나: 언더플로(`≤ x`) → 일반 구간(첫 구간 `[a, b]`, 나머지 `(a, b]`) → 오버플로(`> x`) 순서. */
export interface Bin {
  label: string
  count: number
  kind: 'underflow' | 'range' | 'overflow'
}

/** 구간 수 상한(자동·구간 수 방식). 구간 너비 방식은 이 값보다 많이 나올 수 있어 호출자가 그리기 한도로 거른다. */
export const BIN_COUNT_MAX = 100
/** 구간 너비 방식에서 만들어 보는 구간 수의 상한(너무 작은 너비로 화면이 멈추는 것을 막는다. 넘으면 호출자가 그리지 않는다). */
export const BIN_BUILD_MAX = 1001

const finite = (value: number | string | null): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null)

function sampleStd(values: readonly number[]): number {
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  return Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1))
}

/** 일반 구간의 경계(`edges.length === 구간 수 + 1`). 표본이 하나이거나 모두 같으면 `[min, max]` 구간 하나다. */
function edgesOf(sample: readonly number[], bins: ReportHistogramBins): number[] {
  const min = Math.min(...sample)
  const max = Math.max(...sample)
  const range = max - min
  const width = finite(bins.binWidth)
  const single = [min, max]
  if (range === 0) return single
  if (bins.binMode === 'width' && width !== null && width > 0) {
    const n = Math.min(Math.max(1, Math.ceil(range / width)), BIN_BUILD_MAX)
    return Array.from({ length: n + 1 }, (_, i) => min + i * width)
  }
  let n = 1
  if (bins.binMode === 'count') {
    const count = finite(bins.binCount)
    n = count === null ? 1 : Math.min(Math.max(1, Math.floor(count)), BIN_COUNT_MAX)
  } else if (sample.length > 1) {
    const std = sampleStd(sample)
    // Scott 규칙: 너비 = 3.49 · s · n^(-1/3)
    if (std > 0) n = Math.min(Math.max(1, Math.ceil(range / (3.49 * std * sample.length ** (-1 / 3)))), BIN_COUNT_MAX)
  }
  const step = range / n
  return Array.from({ length: n + 1 }, (_, i) => (i === n ? max : min + i * step))
}

/** v가 들어갈 구간 번호: `v <= edges[i + 1]`인 첫 구간(경계 값은 아래 구간에 든다). */
function binIndex(edges: readonly number[], v: number): number {
  let lo = 0
  let hi = edges.length - 2
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (v <= (edges[mid + 1] ?? Infinity)) hi = mid
    else lo = mid + 1
  }
  return lo
}

/** 표본 값 → 구간별 개수. 빈 값(null)은 빼고, 경계 숫자는 `format`으로 쓴다. 표본이 없으면 빈 목록. */
export function histogramBins(values: readonly (number | null)[], bins: ReportHistogramBins, format: (n: number) => string = String): Bin[] {
  const sample = values.filter((v): v is number => v !== null && Number.isFinite(v))
  if (sample.length === 0) return []
  const under = finite(bins.underflow)
  const over = finite(bins.overflow)
  const inner = sample.filter((v) => (under === null || v > under) && (over === null || v <= over))
  const result: Bin[] = []
  if (under !== null) result.push({ label: `≤ ${format(under)}`, count: sample.filter((v) => v <= under).length, kind: 'underflow' })
  if (inner.length > 0) {
    const edges = edgesOf(inner, bins)
    const counts = Array.from({ length: edges.length - 1 }, () => 0)
    for (const v of inner) {
      const at = binIndex(edges, v)
      counts[at] = (counts[at] ?? 0) + 1
    }
    counts.forEach((count, i) => {
      const [a, b] = [format(edges[i] ?? 0), format(edges[i + 1] ?? 0)]
      result.push({ label: i === 0 ? `[${a}, ${b}]` : `(${a}, ${b}]`, count, kind: 'range' })
    })
  }
  if (over !== null) result.push({ label: `> ${format(over)}`, count: sample.filter((v) => v > over).length, kind: 'overflow' })
  return result
}
