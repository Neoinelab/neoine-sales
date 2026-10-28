import type { ReportLayout, ReportTile } from '../../../shared/model/reportTypes'

/** 결과 배치의 순수 규칙: 놓는 위치 판정, 타일 놓기, 키보드 대응, 보이는 타일. 화면 없이 단위 테스트한다. */

export const DEFAULT_LAYOUT: ReportLayout = { view: 'both', order: ['table', 'chart'], arrange: 'stacked' }

export type DropEdge = 'left' | 'right' | 'top' | 'bottom'

interface Rect {
  left: number
  top: number
  width: number
  height: number
}

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value))

/**
 * 놓은 위치가 타일의 어느 가장자리에 가장 가까운지(정규화 거리, 가로·세로 크기가 달라도 같은 비율로 잰다).
 * 동률이면 left > right > top > bottom. 사각형 밖 좌표는 가장자리로 자른 뒤 잰다.
 */
export function dropEdge(rect: Rect, point: { x: number; y: number }): DropEdge {
  const l = clamp01(rect.width > 0 ? (point.x - rect.left) / rect.width : 0)
  const t = clamp01(rect.height > 0 ? (point.y - rect.top) / rect.height : 0)
  const distances: [DropEdge, number][] = [
    ['left', l],
    ['right', 1 - l],
    ['top', t],
    ['bottom', 1 - t],
  ]
  let best = distances[0] ?? (['left', 0] as [DropEdge, number])
  for (const candidate of distances) if (candidate[1] < best[1]) best = candidate
  return best[0]
}

/** `dragged`를 `target`의 `edge` 쪽에 놓은 배치. 보기 방식은 바꾸지 않는다. 자기 자신 위에는 놓을 수 없어 같은 객체를 돌려준다. */
export function placeTile(layout: ReportLayout, dragged: ReportTile, target: ReportTile, edge: DropEdge): ReportLayout {
  if (dragged === target) return layout
  const before = edge === 'left' || edge === 'top'
  return {
    view: layout.view,
    order: before ? [dragged, target] : [target, dragged],
    arrange: edge === 'left' || edge === 'right' ? 'side_by_side' : 'stacked',
  }
}

/** Alt+화살표 키 → 놓는 가장자리(다른 키는 null). */
export function keyToEdge(key: string): DropEdge | null {
  switch (key) {
    case 'ArrowRight':
      return 'right'
    case 'ArrowLeft':
      return 'left'
    case 'ArrowDown':
      return 'bottom'
    case 'ArrowUp':
      return 'top'
    default:
      return null
  }
}

/** 지금 보일 타일(배치 순서대로). 차트가 없으면 보기 방식과 무관하게 표만 보인다. */
export function visibleTiles(layout: ReportLayout, chartAvailable: boolean): ReportTile[] {
  if (!chartAvailable) return ['table']
  return layout.order.filter((tile) => layout.view === 'both' || layout.view === tile)
}

export function sameLayout(a: ReportLayout, b: ReportLayout): boolean {
  return a.view === b.view && a.arrange === b.arrange && a.order[0] === b.order[0] && a.order[1] === b.order[1]
}

const TILE_NAME: Record<ReportTile, string> = { table: '표', chart: '차트' }

/** 화면 읽기용 안내 문구. 예: "표를 차트 오른쪽에 놓았습니다(한 줄)". */
export function describePlacement(dragged: ReportTile, target: ReportTile, edge: DropEdge): string {
  const where = { left: '왼쪽에', right: '오른쪽에', top: '위에', bottom: '아래에' }[edge]
  const rows = edge === 'left' || edge === 'right' ? '한 줄' : '두 줄'
  return `${TILE_NAME[dragged]}를 ${TILE_NAME[target]} ${where} 놓았습니다(${rows})`
}
