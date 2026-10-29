import { useState, type FormEvent } from 'react'
import { dateValueError } from '../../shared/model/dateText'
import { DateInput } from '../../shared/ui/DateInput'
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
  if (appliedKey !== seen) {
    setSeen(appliedKey)
    setDraft(applied)
    setDateErrors({})
  }
  const set = (patch: Partial<MeetingConditions>) => setDraft((prev) => ({ ...prev, ...patch }))

  function submit(event: FormEvent) {
    event.preventDefault()
    // 틀린 날짜 글자는 검색하지 않고 칸에 문구를 보인다.
    const errors = { from: dateValueError(draft.from) ?? undefined, to: dateValueError(draft.to) ?? undefined }
    if (errors.from || errors.to) {
      setDateErrors(errors)
      return
    }
    setDateErrors({})
    onSearch(draft)
  }

  function reset() {
    setDraft(NO_CONDITIONS)
    setDateErrors({})
    onReset()
  }

  return (
    <form className="meeting-filters" role="search" aria-label="미팅 기록 검색" onSubmit={submit}>
      <TextField label="파트너" name="partner" maxLength={200} value={draft.partner} onChange={(partner) => set({ partner })} />
      <TextField label="Deal" name="deal" maxLength={200} value={draft.deal} onChange={(deal) => set({ deal })} />
      <div className="field meeting-date-range">
        <span>미팅 날짜</span>
        <div className="meeting-date-pair">
          <DateInput aria-label="미팅 날짜 시작" name="from" value={draft.from} error={dateErrors.from} onChange={(from) => set({ from })} />
          <span aria-hidden="true">~</span>
          <DateInput aria-label="미팅 날짜 끝" name="to" value={draft.to} error={dateErrors.to} onChange={(to) => set({ to })} />
        </div>
      </div>
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
    </form>
  )
}
