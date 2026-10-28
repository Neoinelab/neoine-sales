import { Fragment, useEffect, useMemo, useRef, useState, type DragEvent, type KeyboardEvent, type ReactNode } from 'react'
import type { ReportTile, ReportTileArrange } from '../../../shared/model/reportTypes'
import { describePlacement, dropEdge, keyToEdge, type DropEdge } from './layout'
import { TilesContext, type TilesContextValue } from './tilesContext'

interface ResultTilesProps {
  /** 지금 보일 타일(보이는 순서). */
  tiles: readonly ReportTile[]
  arrange: ReportTileArrange
  /** 타일을 다른 타일의 가장자리에 놓았다(끌어서 놓기·Alt+화살표). 끄는 동안에는 부르지 않는다. */
  onPlace: (dragged: ReportTile, target: ReportTile, edge: DropEdge) => void
  /** 타일마다의 내용. 상태(표 페이지 등)가 순서를 바꿔도 남도록 타일 이름을 key로 그린다. */
  nodes: Record<ReportTile, ReactNode>
}

/**
 * 결과 타일 배치와 끌어서 놓기. 한 줄(`is-side`)이면 나란히, 두 줄(`is-stacked`)이면 위아래로 놓는다.
 * 타일이 하나뿐이면 옮길 곳이 없어 끌기·옮기기 버튼이 없다.
 */
export function ResultTiles({ tiles, arrange, onPlace, nodes }: ResultTilesProps) {
  const dragged = useRef<ReportTile | null>(null)
  const [over, setOver] = useState<{ tile: ReportTile; edge: DropEdge } | null>(null)
  const [announcement, setAnnouncement] = useState('')
  const buttons = useRef(new Map<ReportTile, HTMLButtonElement>())
  const focusAfterMove = useRef<ReportTile | null>(null)
  const movable = tiles.length === 2

  // 옮겨서 DOM이 다시 배치되면 키보드로 옮긴 타일의 버튼에 포커스를 되돌린다.
  useEffect(() => {
    const tile = focusAfterMove.current
    if (tile === null) return
    focusAfterMove.current = null
    buttons.current.get(tile)?.focus()
  })

  const place = (from: ReportTile, target: ReportTile, edge: DropEdge) => {
    onPlace(from, target, edge)
    setAnnouncement(describePlacement(from, target, edge))
  }
  const finish = () => {
    dragged.current = null
    setOver(null)
  }

  const context = useMemo<TilesContextValue>(
    () => ({
      movable,
      edgeOf: (tile) => (over?.tile === tile ? over.edge : null),
      onDragStart: (tile, event: DragEvent) => {
        dragged.current = tile
        event.dataTransfer.effectAllowed = 'move'
        event.dataTransfer.setData('text/plain', tile)
      },
      onDragOver: (tile, event: DragEvent) => {
        const from = dragged.current
        if (from === null) return
        if (from === tile) {
          if (over !== null) setOver(null)
          return
        }
        event.preventDefault()
        event.dataTransfer.dropEffect = 'move'
        const edge = dropEdge(event.currentTarget.getBoundingClientRect(), { x: event.clientX, y: event.clientY })
        if (over?.tile !== tile || over.edge !== edge) setOver({ tile, edge })
      },
      onDragLeave: (_tile, event: DragEvent) => {
        // 타일 안의 자식 요소로 옮겨 갈 때는 표시를 지우지 않는다.
        if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return
        setOver(null)
      },
      onDrop: (tile, event: DragEvent) => {
        const from = dragged.current
        if (from === null) return
        event.preventDefault()
        finish()
        if (from === tile) return
        place(from, tile, dropEdge(event.currentTarget.getBoundingClientRect(), { x: event.clientX, y: event.clientY }))
      },
      onDragEnd: finish,
      onMoveKey: (tile, event: KeyboardEvent) => {
        const edge = event.altKey ? keyToEdge(event.key) : null
        const other = tiles.find((t) => t !== tile)
        if (edge === null || other === undefined) return
        event.preventDefault()
        focusAfterMove.current = tile
        place(tile, other, edge)
      },
      moveButtonRef: (tile) => (node) => {
        if (node) buttons.current.set(tile, node)
        else buttons.current.delete(tile)
      },
    }),
    // place·finish는 매 렌더 새로 만들어지지만 부르는 쪽(onPlace)이 최신 레이아웃을 읽는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [movable, over, tiles, onPlace],
  )

  return (
    <TilesContext.Provider value={context}>
      <div className={`report-tiles ${arrange === 'side_by_side' && movable ? 'is-side' : 'is-stacked'}`}>
        {tiles.map((tile) => (
          <Fragment key={tile}>{nodes[tile]}</Fragment>
        ))}
      </div>
      <p className="report-sr" aria-live="polite">
        {announcement}
      </p>
    </TilesContext.Provider>
  )
}
