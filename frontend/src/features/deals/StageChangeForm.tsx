import { useState } from 'react'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField, TextField } from '../../shared/ui/fields'
import { useChangeDealStage, type Deal } from './hooks'
import { DEAL_STAGES, STAGE_LABEL, type DealStage } from './stages'

const MAX_REASON = 500

/** 편의용 검사다. 정본은 서버(422/409)이며 서버 오류는 그대로 보여준다. */
function validate(stage: DealStage, reason: string): string | null {
  if (stage === 'lost' && reason === '') return '실주 사유를 입력하세요.'
  if (reason.length > MAX_REASON) return `사유는 ${MAX_REASON}자 이하로 입력하세요.`
  return null
}

export function StageChangeForm({ deal }: { deal: Deal }) {
  const change = useChangeDealStage(deal.id)
  const options = DEAL_STAGES.filter((s) => s !== deal.stage)
  const [picked, setPicked] = useState<DealStage | ''>('')
  const [reason, setReason] = useState('')
  const [hint, setHint] = useState<string | null>(null)
  // 단계가 바뀌어 선택값이 현재 단계와 같아지면 미선택('')으로 되돌린다.
  const stage = options.find((s) => s === picked)
  const isLost = stage === 'lost'

  return (
    <section aria-label="단계 변경">
      <h2>단계 변경</h2>
      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault()
          if (!stage) return
          const trimmed = reason.trim()
          const problem = validate(stage, trimmed)
          setHint(problem)
          if (problem) return
          change.mutate(
            { stage, reason: trimmed === '' ? null : trimmed },
            {
              onSuccess: () => {
                setReason('')
                setPicked('')
              },
            },
          )
        }}
      >
        {hint && (
          <p role="alert" className="error">
            {hint}
          </p>
        )}
        <ErrorBanner error={change.error} />
        <SelectField label="변경할 단계" name="stage" value={stage ?? ''} onChange={(v) => setPicked(v as DealStage | '')}>
          <option value="">선택하세요</option>
          {options.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </SelectField>
        <TextField
          label={isLost ? '실주 사유(필수)' : '사유'}
          name="reason"
          value={reason}
          onChange={setReason}
          required={isLost}
        />
        <div className="actions">
          <button type="submit" className="primary" disabled={change.isPending || !stage}>
            단계 변경
          </button>
        </div>
      </form>
    </section>
  )
}
