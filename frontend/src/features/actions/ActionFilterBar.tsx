import { useState } from 'react'
import { dayStart } from '../../shared/format'
import { SelectField, TextField } from '../../shared/ui/fields'
import type { ActionFilters } from './hooks'
import { ACTION_TYPES, type ActionType } from './labels'

interface Props {
  onSearch: (filters: ActionFilters) => void
}

/** 검색 조건 입력. 기간은 날짜로 받고, 끝 날짜는 그날 하루를 포함하도록 다음 날 0시 미만으로 보낸다. */
export function ActionFilterBar({ onSearch }: Props) {
  const [type, setType] = useState('')
  const [actor, setActor] = useState('')
  const [keyword, setKeyword] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  return (
    <form
      className="filters"
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        onSearch({
          action_type: (type || undefined) as ActionType | undefined,
          actor: actor.trim() || undefined,
          keyword: keyword.trim() || undefined,
          acted_from: from ? dayStart(from) : undefined,
          acted_to: to ? dayStart(to, 1) : undefined,
        })
      }}
    >
      <SelectField label="유형" name="type" value={type} onChange={setType}>
        <option value="">전체</option>
        {ACTION_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </SelectField>
      <TextField label="활동자" name="actor" value={actor} onChange={setActor} />
      <TextField label="검색어(제목·내용)" name="keyword" value={keyword} onChange={setKeyword} />
      <TextField label="시작일" name="from" type="date" value={from} onChange={setFrom} />
      <TextField label="종료일" name="to" type="date" value={to} onChange={setTo} />
      <button type="submit">검색</button>
    </form>
  )
}
