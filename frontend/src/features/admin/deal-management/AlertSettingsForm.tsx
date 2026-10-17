import { useId, useState } from 'react'
import { useAlertSettings, useSaveAlertSettings } from '../../../data/alerts'
import { formatDateTime } from '../../../shared/format'
import { STALE_DAYS_MAX, STALE_DAYS_MIN, STALE_DAYS_RANGE_MESSAGE } from '../../../shared/model/constants'
import { userLabel } from '../../../shared/model/period'
import type { AlertSettings } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'

/** 입력 문자열 → 1~365 정수. 범위 밖·빈 값·소수는 null(서버 판정이 최종이고 화면은 저장 버튼만 막는다). */
function parseDays(text: string): number | null {
  if (text.trim() === '') return null
  const value = Number(text)
  return Number.isInteger(value) && value >= STALE_DAYS_MIN && value <= STALE_DAYS_MAX ? value : null
}

function Form({ saved }: { saved: AlertSettings }) {
  const inputId = useId()
  const hintId = useId()
  const save = useSaveAlertSettings()
  const [text, setText] = useState(String(saved.staleDays))
  const days = parseDays(text)
  const invalid = days === null
  const unchanged = days === saved.staleDays

  return (
    <form
      noValidate
      aria-label="경고 기준 변경"
      onSubmit={(e) => {
        e.preventDefault()
        if (days !== null && !unchanged) save.mutate(days)
      }}
    >
      <ErrorBanner error={save.error} />
      <div className="field">
        <label htmlFor={inputId}>미업데이트 기준(일)</label>
        <input
          id={inputId}
          type="number"
          name="stale_days"
          min={STALE_DAYS_MIN}
          max={STALE_DAYS_MAX}
          step={1}
          value={text}
          aria-invalid={invalid}
          aria-describedby={hintId}
          onChange={(e) => {
            save.reset()
            setText(e.target.value)
          }}
        />
      </div>
      <p id={hintId} className="hint">마지막 업데이트 후 이 일수 이상 지나면 Deal에 &apos;미업데이트&apos; 표시가 붙습니다. (1~365일)</p>
      {invalid && <p className="field-error">{STALE_DAYS_RANGE_MESSAGE}</p>}
      {saved.updatedAt !== null && (
        <p className="hint">{`마지막 저장 ${saved.updatedBy ? userLabel(saved.updatedBy) : '-'} · ${formatDateTime(saved.updatedAt)}`}</p>
      )}
      <div className="actions">
        <button type="submit" className="primary" disabled={invalid || unchanged || save.isPending}>
          저장
        </button>
      </div>
    </form>
  )
}

/** Deal 관리 4번째 탭: 미업데이트 기준(일). 저장은 admin만(탭 자체가 admin 화면). */
export function AlertSettingsForm() {
  const settings = useAlertSettings()
  const saved = settings.data
  return (
    <section className="admin-card" aria-label="경고 기준">
      <ErrorBanner error={settings.error} />
      {settings.isPending && <p className="hint">불러오는 중…</p>}
      {saved && <Form key={`${saved.staleDays}|${saved.updatedAt ?? ''}`} saved={saved} />}
    </section>
  )
}
