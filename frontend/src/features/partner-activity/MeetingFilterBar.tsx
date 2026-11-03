import { useRef, useState, type FormEvent } from 'react'
import { useFreshUpdatedPeriods, useUpdatedPeriods } from '../../data/deals'
import { dateValueError } from '../../shared/model/dateText'
import { resolvePeriodChoice, type PastPeriodChoice } from '../../shared/model/periodChoice'
import { selectedUpdatedPeriod } from '../../shared/model/updatedPeriod'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { PeriodField } from '../../shared/ui/PeriodField'
import { TextField } from '../../shared/ui/fields'
import { UserSelect } from '../../shared/ui/UserSelect'
import { NO_CONDITIONS, type MeetingConditions } from './useMeetingSearchParams'

interface MeetingFilterBarProps {
  /** URL의 현재 조건. 바깥에서 바뀌면(뒤로 가기·초기화) 입력 칸도 따라간다. */
  applied: MeetingConditions
  onSearch: (next: MeetingConditions) => void
  onReset: () => void
}

/** 미팅 기록 검색 조건. 텍스트·날짜·작성자를 모아 검색 버튼(또는 텍스트 칸의 Enter)으로 한 번에 적용한다. */
export function MeetingFilterBar({ applied, onSearch, onReset }: MeetingFilterBarProps) {
  const [draft, setDraft] = useState<MeetingConditions>(applied)
  // 바깥 조건이 값으로 바뀐 때만 칸을 맞춘다(정렬만 바뀌어 새 객체가 와도 아직 검색하지 않은 입력을 지키지 않는다).
  const appliedKey = JSON.stringify(applied)
  const [seen, setSeen] = useState(appliedKey)
  const [dateErrors, setDateErrors] = useState<{ from?: string; to?: string }>({})
  const periodsQuery = useUpdatedPeriods()
  const fetchFresh = useFreshUpdatedPeriods()
  // 사용자가 고른 기간 선택. null이면 입력 칸의 날짜에서 프리셋 일치 여부로 정한다(selectedUpdatedPeriod).
  const [picked, setPicked] = useState<PastPeriodChoice | null>(null)
  // 검색·초기화마다 올린다. 늦게 온 이전 프리셋 응답은 순번이 달라 버린다.
  const searchSeq = useRef(0)
  // '직접 지정'으로 검색한 날짜에 묶인 키(Deals customKey와 같은 규칙). 적용 날짜가 바깥에서 바뀌면 키가 달라져 닫힌다.
  const [customKey, setCustomKey] = useState<string | null>(null)
  const customOpen = customKey === `${applied.from}|${applied.to}`
  const [refreshError, setRefreshError] = useState<unknown>(null)
  if (appliedKey !== seen) {
    setSeen(appliedKey)
    setDraft(applied)
    setDateErrors({})
    setPicked(null)
  }
  const set = (patch: Partial<MeetingConditions>) => setDraft((prev) => ({ ...prev, ...patch }))
  const choice: PastPeriodChoice = picked ?? (customOpen ? 'custom' : selectedUpdatedPeriod(draft.from, draft.to, periodsQuery.data?.periods))

  function choosePeriod(next: string) {
    const value = next as PastPeriodChoice
    setPicked(value)
    setDateErrors({})
    // 전체는 날짜 조건을 없애고, 프리셋은 검색할 때 서버에서 새로 풀어 채운다.
    if (value === '') set({ from: '', to: '' })
  }

  /** 프리셋이면 그 시점에 서버에서 새로 받아 날짜로 푼다(자정 경과 대비). 실패하면 조건을 바꾸지 않는다. */
  async function submit(event: FormEvent) {
    event.preventDefault()
    const seq = ++searchSeq.current
    setRefreshError(null)
    let conditions = draft
    if (choice !== '' && choice !== 'custom') {
      try {
        const resolved = resolvePeriodChoice(choice, await fetchFresh())
        if (seq !== searchSeq.current) return
        // 고른 키가 없으면 Deals처럼 날짜 조건을 비우고 나머지 조건으로 검색한다.
        conditions = { ...draft, from: resolved?.from ?? '', to: resolved?.to ?? '' }
      } catch (error) {
        if (seq === searchSeq.current) setRefreshError(error)
        return
      }
    }
    // 틀린 날짜 글자는 검색하지 않고 칸에 문구를 보인다.
    const errors = { from: dateValueError(conditions.from) ?? undefined, to: dateValueError(conditions.to) ?? undefined }
    if (errors.from || errors.to) {
      setDateErrors(errors)
      return
    }
    setDateErrors({})
    if (choice === 'custom') setCustomKey(`${conditions.from}|${conditions.to}`)
    onSearch(conditions)
  }

  function reset() {
    searchSeq.current += 1
    setRefreshError(null)
    setPicked(null)
    setDraft(NO_CONDITIONS)
    setDateErrors({})
    onReset()
  }

  return (
    <form className="meeting-filters" role="search" aria-label="미팅 기록 검색" onSubmit={(e) => void submit(e)}>
      <TextField label="파트너" name="partner" maxLength={200} value={draft.partner} onChange={(partner) => set({ partner })} />
      <PeriodField
        label="미팅 날짜"
        value={choice}
        onChange={(v) => choosePeriod(v)}
        presets={periodsQuery.data}
        from={draft.from}
        to={draft.to}
        onFromChange={(from) => set({ from })}
        onToChange={(to) => set({ to })}
        fromError={dateErrors.from}
        toError={dateErrors.to}
      />
      <TextField label="미팅 내용" name="content" maxLength={100} value={draft.content} onChange={(content) => set({ content })} />
      <UserSelect label="작성자" name="author" value={draft.author} onChange={(author) => set({ author })} includeResigned />
      <div className="filter-buttons">
        <button type="submit" className="primary">
          검색
        </button>
        <button type="button" onClick={reset}>
          초기화
        </button>
      </div>
      {periodsQuery.data === undefined && <ErrorBanner error={periodsQuery.error} />}
      <ErrorBanner error={refreshError} />
    </form>
  )
}
