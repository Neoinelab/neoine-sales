import { useState } from 'react'
import { fromLocalInput, toLocalInput } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField, TextArea, TextField } from '../../shared/ui/fields'
import { useUserChoice } from '../users/options'
import { UserSelect } from '../users/UserSelect'
import { useSaveAction, type DealAction } from './hooks'
import { ACTION_TYPES, type ActionType } from './labels'

interface Props {
  dealId: string
  initial?: DealAction
  onDone: () => void
}

export function ActionForm({ dealId, initial, onDone }: Props) {
  const save = useSaveAction(dealId)
  const [form, setForm] = useState({
    action_type: (initial?.action_type ?? 'meeting') as string,
    action: initial?.action ?? '',
    next_action: initial?.next_action ?? '',
    due_date: initial?.due_date ?? '',
    memo: initial?.memo ?? '',
    acted_at: toLocalInput(initial?.acted_at ?? new Date().toISOString()),
  })
  // 신규는 로그인 사용자를 초기 선택하고, 수정은 기존 활동자를 유지한다.
  const [actorId, setActorId] = useUserChoice(initial?.actor.id)
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate(
          {
            id: initial?.id,
            body: {
              ...form,
              actor_user_id: actorId,
              action_type: form.action_type as ActionType,
              acted_at: fromLocalInput(form.acted_at),
            },
          },
          { onSuccess: onDone },
        )
      }}
    >
      <h3>{initial ? '활동 수정' : '활동 기록'}</h3>
      <ErrorBanner error={save.error} />
      <SelectField label="유형" name="action_type" value={form.action_type} onChange={set('action_type')}>
        {ACTION_TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </SelectField>
      <TextField label="진행내역" name="action" value={form.action} onChange={set('action')} required />
      <TextField label="다음 진행 계획" name="next_action" value={form.next_action} onChange={set('next_action')} required />
      <TextField label="계획일" name="due_date" type="date" value={form.due_date} onChange={set('due_date')} required />
      <TextArea label="메모" name="memo" value={form.memo} onChange={set('memo')} />
      <TextField label="활동 일시" name="acted_at" type="datetime-local" value={form.acted_at} onChange={set('acted_at')} required />
      <UserSelect label="활동자" name="actor_user_id" value={actorId} onChange={setActorId} current={initial?.actor} required />
      <div className="actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          저장
        </button>
        <button type="button" onClick={onDone}>
          취소
        </button>
      </div>
    </form>
  )
}
