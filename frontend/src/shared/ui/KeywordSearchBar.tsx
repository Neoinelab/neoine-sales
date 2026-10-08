import { useState } from 'react'
import { TextField } from './fields'

interface Props {
  onSearch: (keyword: string | undefined) => void
}

/** 키워드 하나로 검색하는 폼(고객·파트너 공용). 빈 값은 undefined로 전달한다. */
export function KeywordSearchBar({ onSearch }: Props) {
  const [keyword, setKeyword] = useState('')
  return (
    <form
      className="filters"
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        onSearch(keyword.trim() || undefined)
      }}
    >
      <TextField label="검색어" name="keyword" value={keyword} onChange={setKeyword} />
      <button type="submit">검색</button>
    </form>
  )
}
