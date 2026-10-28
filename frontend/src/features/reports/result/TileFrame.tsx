import type { ReactNode } from 'react'
import type { ReportTile } from '../../../shared/model/reportTypes'
import { useTiles } from './tilesContext'

const NAME: Record<ReportTile, string> = { table: '표', chart: '차트' }

interface TileFrameProps {
  tile: ReportTile
  /** 머리의 제목 오른쪽에 놓일 것(요약 줄, 체크박스, 버튼). */
  head?: ReactNode
  children: ReactNode
}

/**
 * 결과 타일의 틀: 머리(끄는 손잡이 + 제목 + 옮기기 버튼)와 본문.
 * 끌기는 머리에서 시작하고 놓기는 타일 전체가 받는다. 끌고 있는 동안 놓일 가장자리에 `is-drop-*` 표시가 붙는다.
 */
export function TileFrame({ tile, head, children }: TileFrameProps) {
  const dnd = useTiles()
  const edge = dnd.edgeOf(tile)
  return (
    <section
      className={`report-tile${edge ? ` is-drop-${edge}` : ''}`}
      aria-label={`${NAME[tile]} 타일`}
      onDragOver={(event) => dnd.onDragOver(tile, event)}
      onDragLeave={(event) => dnd.onDragLeave(tile, event)}
      onDrop={(event) => dnd.onDrop(tile, event)}
    >
      <div className={`report-tile-head${dnd.movable ? ' is-movable' : ''}`} draggable={dnd.movable} onDragStart={(event) => dnd.onDragStart(tile, event)} onDragEnd={dnd.onDragEnd}>
        <h3 className="report-tile-title">{NAME[tile]}</h3>
        <div className="report-tile-tools">{head}</div>
        {dnd.movable && (
          <button
            type="button"
            className="report-tile-move"
            ref={dnd.moveButtonRef(tile)}
            aria-label={`${NAME[tile]} 타일 옮기기`}
            title="끌어서 옮기거나 Alt+화살표 키로 옮깁니다"
            onKeyDown={(event) => dnd.onMoveKey(tile, event)}
          >
            ⠿
          </button>
        )}
      </div>
      <div className="report-tile-body">{children}</div>
    </section>
  )
}
