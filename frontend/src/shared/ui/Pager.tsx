interface PagerProps {
  offset: number
  limit: number
  /** 현재 페이지 항목 수. total이 없을 때 "count < limit이면 마지막"으로 판단한다(기존 호출 호환). */
  count?: number
  /** 필터 적용 후 전체 건수(`Page.total`). 있으면 이것으로 마지막 페이지를 판단한다. */
  total?: number
  onChange: (offset: number) => void
}

export function Pager({ offset, limit, count, total, onChange }: PagerProps) {
  const last = total !== undefined ? offset + limit >= total : (count ?? 0) < limit
  return (
    <nav className="pager" aria-label="페이지">
      <button type="button" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        이전
      </button>
      <span>{Math.floor(offset / limit) + 1} 페이지</span>
      <button type="button" disabled={last} onClick={() => onChange(offset + limit)}>
        다음
      </button>
    </nav>
  )
}
