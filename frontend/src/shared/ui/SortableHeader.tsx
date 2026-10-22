import type { SortOrder } from '../model/types'
import './ui.css'

interface SortableHeaderProps {
  label: string
  /** 지금 정렬 기준인 열인지. */
  active: boolean
  order: SortOrder
  /** 없으면 정렬할 수 없는 열이라 버튼과 aria-sort 없이 이름만 보인다. */
  onSort?: () => void
}

/** 정렬 가능한 표 머리글(th). 활성 열에만 aria-sort와 방향 표시(data-dir)를 둔다. */
export function SortableHeader({ label, active, order, onSort }: SortableHeaderProps) {
  const sorted = active && onSort !== undefined
  return (
    <th scope="col" aria-sort={sorted ? (order === 'asc' ? 'ascending' : 'descending') : undefined}>
      {onSort ? (
        <button type="button" className="th-sort" data-dir={sorted ? order : undefined} onClick={onSort}>
          {label}
        </button>
      ) : (
        label
      )}
    </th>
  )
}
