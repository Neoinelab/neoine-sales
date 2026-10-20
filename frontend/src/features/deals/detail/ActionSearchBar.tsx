import { useState, type FormEvent } from 'react'
import { useActionTypes } from '../../../data/actionTypes'
import { NEXT_ACTION_STATUS_FILTER_OPTIONS, isNextActionStatusFilter } from '../../../shared/model/nextActionStatus'
import type { ActionQuery, ActionSort, NextActionStatusFilter } from '../../../shared/model/types'
import { UserSelect } from '../../../shared/ui/UserSelect'
import './detail.css'

interface ActionSearchBarProps {
  onSearch: (query: ActionQuery) => void
}

interface Draft {
  typeId: string
  actorId: string
  keyword: string
  actedFrom: string
  actedTo: string
  dueFrom: string
  dueTo: string
  nextStatus: NextActionStatusFilter | ''
  sort: ActionSort
}

const EMPTY: Draft = { typeId: '', actorId: '', keyword: '', actedFrom: '', actedTo: '', dueFrom: '', dueTo: '', nextStatus: '', sort: 'actedDesc' }

/** 채워진 조건만 질의로 만든다(빈 값은 보내지 않는다). */
function toActionQuery(draft: Draft): ActionQuery {
  const query: ActionQuery = { sort: draft.sort }
  if (draft.typeId) query.typeId = draft.typeId
  if (draft.actorId) query.actorId = draft.actorId
  if (draft.keyword.trim()) query.keyword = draft.keyword.trim()
  if (draft.actedFrom) query.actedFrom = draft.actedFrom
  if (draft.actedTo) query.actedTo = draft.actedTo
  if (draft.dueFrom) query.dueFrom = draft.dueFrom
  if (draft.dueTo) query.dueTo = draft.dueTo
  if (draft.nextStatus) query.nextActionStatus = draft.nextStatus
  return query
}

/** Actions 검색: 유형 / 담당자 / 키워드 / 수행일 / 기한 범위 / Next Action 상태 / 정렬. */
export function ActionSearchBar({ onSearch }: ActionSearchBarProps) {
  const types = useActionTypes().data ?? []
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
        <select value={draft.typeId} onChange={(e) => set('typeId', e.target.value)}>
          <option value="">전체</option>
          {types.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
      </label>
      <UserSelect label="담당자" name="actor" value={draft.actorId} onChange={(v) => set('actorId', v)} includeResigned />
      <label className="field">
        <span>키워드</span>
        <input maxLength={100} value={draft.keyword} onChange={(e) => set('keyword', e.target.value)} placeholder="진행사항·Next Action·Memo" />
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
        <span>Next Action 상태</span>
        <select
          value={draft.nextStatus}
          onChange={(e) => set('nextStatus', isNextActionStatusFilter(e.target.value) ? e.target.value : '')}
        >
          {NEXT_ACTION_STATUS_FILTER_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
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
