interface PagerProps {
  offset: number
  limit: number
  count: number
  onChange: (offset: number) => void
}

export function Pager({ offset, limit, count, onChange }: PagerProps) {
  return (
    <nav className="pager" aria-label="페이지">
      <button type="button" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        이전
      </button>
      <span>{Math.floor(offset / limit) + 1} 페이지</span>
      <button type="button" disabled={count < limit} onClick={() => onChange(offset + limit)}>
        다음
      </button>
    </nav>
  )
}
