import { useState } from 'react'
import { dayStart } from '../../shared/format'
import { SelectField, TextField } from '../../shared/ui/fields'
import { UserSelect } from '../users/UserSelect'
import type { ActionFilters } from './hooks'
import { ACTION_SORTS, ACTION_TYPES, type ActionType } from './labels'

interface Props {
  onSearch: (filters: ActionFilters) => void
}

/** 검색 조건 입력. 기간은 날짜로 받고, 끝 날짜는 그날 하루를 포함하도록 다음 날 0시 미만으로 보낸다. */
export function ActionFilterBar({ onSearch }: Props) {
  const [type, setType] = useState('')
  const [actorId, setActorId] = useState('')
  const [keyword, setKeyword] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [dueFrom, setDueFrom] = useState('')
  const [dueTo, setDueTo] = useState('')
  const [sort, setSort] = useState('')

  return (
    <form
      className="filters"
      role="search"
      onSubmit={(e) => {
        e.preventDefault()
        onSearch({
          action_type: (type || undefined) as ActionType | undefined,
          actor_user_id: actorId || undefined,
          keyword: keyword.trim() || undefined,
          acted_from: from ? dayStart(from) : undefined,
          acted_to: to ? dayStart(to, 1) : undefined,
          due_from: dueFrom || undefined,
          due_to: dueTo || undefined,
          sort: (sort || undefined) as ActionFilters['sort'],
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
      <UserSelect label="활동자" name="actor_user_id" value={actorId} onChange={setActorId} includeResigned />
      <TextField label="검색어(진행내역·계획·메모)" name="keyword" value={keyword} onChange={setKeyword} />
      <TextField label="시작일" name="from" type="date" value={from} onChange={setFrom} />
      <TextField label="종료일" name="to" type="date" value={to} onChange={setTo} />
      <TextField label="계획일 시작" name="due_from" type="date" value={dueFrom} onChange={setDueFrom} />
      <TextField label="계획일 종료" name="due_to" type="date" value={dueTo} onChange={setDueTo} />
      <SelectField label="정렬" name="sort" value={sort} onChange={setSort}>
        <option value="">진행일 최신순</option>
        {ACTION_SORTS.filter((o) => o.value !== 'acted_at_desc').map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </SelectField>
      <button type="submit">검색</button>
    </form>
  )
}
