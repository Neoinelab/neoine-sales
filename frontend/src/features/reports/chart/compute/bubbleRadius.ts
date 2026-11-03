const MIN_RADIUS = 4
const SPAN = 26

/** 거품 반지름(px) = 4 + 26 · sqrt(크기 / 최대 크기): 면적이 크기에 비례하고 최대는 30px. 0 이하·빈 값 자리는 null(그리지 않음). */
export function bubbleRadius(sizes: readonly (number | null)[]): { radii: (number | null)[]; skipped: number } {
  const positive = sizes.filter((s): s is number => s !== null && s > 0)
  const largest = Math.max(0, ...positive)
  const radii = sizes.map((size) => (size !== null && size > 0 ? MIN_RADIUS + SPAN * Math.sqrt(size / largest) : null))
  return { radii, skipped: sizes.length - positive.length }
}
