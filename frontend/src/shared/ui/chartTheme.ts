/** Chart.js 요소를 등록하지 않는 차트 공용 값(등록은 화면별 `chartSetup`·`chartRegistry`가 한다). */

/** 열(계열) 하나에 하나씩 쓰는 색(순서대로, 넘치면 되풀이). 밝은 배경과 어두운 배경 모두에서 구분된다. */
export const SERIES_COLORS = ['#94a3b8', '#60a5fa', '#34d399', '#fbbf24', '#f472b6', '#a78bfa', '#fb923c', '#2dd4bf', '#f87171', '#a3e635'] as const

/** 캔버스는 CSS 변수를 못 읽으므로 현재 테마의 글자·눈금선 색을 직접 읽는다. 읽지 못하면(테스트 등) 기본 색. */
export function chartTheme(): { text: string; grid: string } {
  const style = typeof document === 'undefined' ? null : getComputedStyle(document.documentElement)
  const read = (name: string, fallback: string) => style?.getPropertyValue(name).trim() || fallback
  return { text: read('--text', '#374151'), grid: read('--line', '#e5e7eb') }
}
