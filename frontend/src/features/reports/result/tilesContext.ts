import { createContext, useContext, type DragEvent, type KeyboardEvent } from 'react'
import type { ReportTile } from '../../../shared/model/reportTypes'
import type { DropEdge } from './layout'

/** 타일 틀이 끌어서 놓기·키보드 옮기기를 위해 부모(`ResultTiles`)에서 받는 것. */
export interface TilesContextValue {
  /** 두 타일이 함께 보일 때만 옮길 수 있다. */
  movable: boolean
  /** 끄는 동안 이 타일에 놓일 가장자리(표시용). 아니면 null. */
  edgeOf: (tile: ReportTile) => DropEdge | null
  onDragStart: (tile: ReportTile, event: DragEvent) => void
  onDragOver: (tile: ReportTile, event: DragEvent) => void
  onDragLeave: (tile: ReportTile, event: DragEvent) => void
  onDrop: (tile: ReportTile, event: DragEvent) => void
  onDragEnd: () => void
  onMoveKey: (tile: ReportTile, event: KeyboardEvent) => void
  /** 키보드로 옮긴 뒤 포커스를 되돌릴 "옮기기" 버튼을 등록한다. */
  moveButtonRef: (tile: ReportTile) => (node: HTMLButtonElement | null) => void
}

export const TilesContext = createContext<TilesContextValue | null>(null)

export function useTiles(): TilesContextValue {
  const value = useContext(TilesContext)
  if (!value) throw new Error('타일은 ResultTiles 안에서만 쓸 수 있습니다.')
  return value
}
