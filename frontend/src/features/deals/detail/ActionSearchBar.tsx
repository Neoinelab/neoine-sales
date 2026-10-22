import { useRef, useState, type FormEvent } from 'react'
import { useActionTypes } from '../../../data/actionTypes'
import { useFreshUpdatedPeriods, useUpdatedPeriods } from '../../../data/deals'
import { resolvePeriodChoice, type DuePeriodChoice, type PastPeriodChoice } from '../../../shared/model/periodChoice'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { NEXT_ACTION_STATUS_FILTER_OPTIONS, isNextActionStatusFilter } from '../../../shared/model/nextActionStatus'
import type { ActionQuery, ActionSort, NextActionStatusFilter, UpdatedPeriods } from '../../../shared/model/types'
import { UserSelect } from '../../../shared/ui/UserSelect'
import { ActionPeriodField } from './ActionPeriodField'
import './detail.css'
import { parseId } from '../../../shared/model/ids'

interface ActionSearchBarProps {
  onSearch: (query: ActionQuery) => void
}

interface Draft {
  typeId: string
  actorId: string
  keyword: string
  actedPeriod: PastPeriodChoice
  duePeriod: DuePeriodChoice
  /** '직접 지정'일 때만 쓰는 날짜. */
  actedFrom: string
  actedTo: string
  dueFrom: string
  dueTo: string
  nextStatus: NextActionStatusFilter | ''
  sort: ActionSort
}

const EMPTY: Draft = { typeId: '', actorId: '', keyword: '', actedPeriod: '', duePeriod: '', actedFrom: '', actedTo: '', dueFrom: '', dueTo: '', nextStatus: '', sort: 'actedDesc' }

/** 채워진 조건만 질의로 만든다(빈 값은 보내지 않는다). 프리셋은 서버가 준 날짜로 푼다. */
function toActionQuery(draft: Draft, presets: UpdatedPeriods | undefined): ActionQuery {
  const query: ActionQuery = { sort: draft.sort }
  const typeId = parseId(draft.typeId)
  if (typeId !== undefined) query.typeId = typeId
  const actorId = parseId(draft.actorId)
  if (actorId !== undefined) query.actorId = actorId
  if (draft.keyword.trim()) query.keyword = draft.keyword.trim()
  const acted = presets ? resolvePeriodChoice(draft.actedPeriod, presets) : undefined
  if (acted) {
    query.actedFrom = acted.from
    query.actedTo = acted.to
  } else if (draft.actedPeriod === 'custom') {
    if (draft.actedFrom) query.actedFrom = draft.actedFrom
    if (draft.actedTo) query.actedTo = draft.actedTo
  }
  const due = presets ? resolvePeriodChoice(draft.duePeriod, presets) : undefined
  if (due) {
    query.dueFrom = due.from
    query.dueTo = due.to
  } else if (draft.duePeriod === 'custom') {
    if (draft.dueFrom) query.dueFrom = draft.dueFrom
    if (draft.dueTo) query.dueTo = draft.dueTo
  }
  if (draft.nextStatus) query.nextActionStatus = draft.nextStatus
  return query
}

/** Actions 검색: 유형 / 담당자 / 키워드 / 수행일 / 기한 범위 / Next Action 상태 / 정렬. */
export function ActionSearchBar({ onSearch }: ActionSearchBarProps) {
  const types = useActionTypes().data ?? []
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const periodsQuery = useUpdatedPeriods()
  const fetchFresh = useFreshUpdatedPeriods()
  // 검색·초기화마다 올린다. 늦게 온 이전 프리셋 응답은 순번이 달라 버린다.
  const searchSeq = useRef(0)
  const [refreshError, setRefreshError] = useState<unknown>(null)
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => ({ ...d, [key]: value }))

  /** 프리셋이 있으면 그 시점에 서버에서 새로 받아 날짜를 푼다(자정 경과 대비). 실패하면 질의를 바꾸지 않는다. */
  async function submit(event: FormEvent) {
    event.preventDefault()
    const seq = ++searchSeq.current
    setRefreshError(null)
    const usesPreset = (draft.actedPeriod !== '' && draft.actedPeriod !== 'custom') || (draft.duePeriod !== '' && draft.duePeriod !== 'custom')
    let presets: UpdatedPeriods | undefined
    if (usesPreset) {
      try {
        presets = await fetchFresh()
      } catch (error) {
        if (seq === searchSeq.current) setRefreshError(error)
        return
      }
      if (seq !== searchSeq.current) return
    }
    onSearch(toActionQuery(draft, presets))
  }

  return (
    <form role="search" aria-label="Action 검색" className="dd-search" onSubmit={(e) => void submit(e)}>
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
      <ActionPeriodField
        label="수행일"
        value={draft.actedPeriod}
        onChange={(v) => set('actedPeriod', v as PastPeriodChoice)}
        presets={periodsQuery.data}
        from={draft.actedFrom}
        to={draft.actedTo}
        onFromChange={(v) => set('actedFrom', v)}
        onToChange={(v) => set('actedTo', v)}
      />
      <ActionPeriodField
        label="기한"
        value={draft.duePeriod}
        onChange={(v) => set('duePeriod', v)}
        presets={periodsQuery.data}
        withUpcoming
        from={draft.dueFrom}
        to={draft.dueTo}
        onFromChange={(v) => set('dueFrom', v)}
        onToChange={(v) => set('dueTo', v)}
      />
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
      {periodsQuery.data === undefined && <ErrorBanner error={periodsQuery.error} />}
      <ErrorBanner error={refreshError} />
      <div className="actions">
        <button type="submit" className="primary">
          검색
        </button>
        <button
          type="button"
          onClick={() => {
            searchSeq.current += 1
            setRefreshError(null)
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
