import { useState, type FormEvent } from 'react'
import { ACTION_TYPES, type ActionType } from '../../../shared/model/constants'
import type { ActionQuery, ActionSort } from '../../../shared/model/types'
import { UserSelect } from '../../../shared/ui/UserSelect'
import './detail.css'

interface ActionSearchBarProps {
  onSearch: (query: ActionQuery) => void
}

interface Draft {
  type: ActionType | ''
  actorId: string
  keyword: string
  actedFrom: string
  actedTo: string
  dueFrom: string
  dueTo: string
  sort: ActionSort
}

const EMPTY: Draft = { type: '', actorId: '', keyword: '', actedFrom: '', actedTo: '', dueFrom: '', dueTo: '', sort: 'actedDesc' }

/** 채워진 조건만 질의로 만든다(빈 값은 보내지 않는다). */
function toActionQuery(draft: Draft): ActionQuery {
  const query: ActionQuery = { sort: draft.sort }
  if (draft.type) query.type = draft.type
  if (draft.actorId) query.actorId = draft.actorId
  if (draft.keyword.trim()) query.keyword = draft.keyword.trim()
  if (draft.actedFrom) query.actedFrom = draft.actedFrom
  if (draft.actedTo) query.actedTo = draft.actedTo
  if (draft.dueFrom) query.dueFrom = draft.dueFrom
  if (draft.dueTo) query.dueTo = draft.dueTo
  return query
}

/** Actions 검색: 유형 / 담당자 / 키워드 / 수행일 / 기한 범위 / 정렬 6조건. */
export function ActionSearchBar({ onSearch }: ActionSearchBarProps) {
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }))

  function submit(event: FormEvent) {
    event.preventDefault()
    onSearch(toActionQuery(draft))
  }

  return (
    <form role="search" aria-label="Action 검색" className="dd-search" onSubmit={submit}>
      <label className="field">
        <span>유형</span>
        <select value={draft.type} onChange={(e) => set('type', e.target.value as ActionType | '')}>
          <option value="">전체</option>
          {ACTION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <UserSelect label="담당자" name="actor" value={draft.actorId} onChange={(v) => set('actorId', v)} includeResigned />
      <label className="field">
        <span>키워드</span>
        <input value={draft.keyword} onChange={(e) => set('keyword', e.target.value)} placeholder="진행사항·Next Action·Memo" />
      </label>
      <label className="field">
        <span>수행일 시작</span>
        <input type="date" value={draft.actedFrom} onChange={(e) => set('actedFrom', e.target.value)} />
      </label>
      <label className="field">
        <span>수행일 끝</span>
        <input type="date" value={draft.actedTo} onChange={(e) => set('actedTo', e.target.value)} />
      </label>
      <label className="field">
        <span>기한 시작</span>
        <input type="date" value={draft.dueFrom} onChange={(e) => set('dueFrom', e.target.value)} />
      </label>
      <label className="field">
        <span>기한 끝</span>
        <input type="date" value={draft.dueTo} onChange={(e) => set('dueTo', e.target.value)} />
      </label>
      <label className="field">
        <span>정렬</span>
        <select value={draft.sort} onChange={(e) => set('sort', e.target.value as ActionSort)}>
          <option value="actedDesc">수행일 최신순</option>
          <option value="actedAsc">수행일 오래된순</option>
          <option value="dueAsc">기한 임박순</option>
        </select>
      </label>
      <div className="actions">
        <button type="submit" className="primary">
          검색
        </button>
        <button
          type="button"
          onClick={() => {
            setDraft(EMPTY)
            onSearch({})
          }}
        >
          초기화
        </button>
      </div>
    </form>
  )
}
