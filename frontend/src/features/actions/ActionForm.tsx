import { useState } from 'react'
import { fromLocalInput, toLocalInput } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField, TextArea, TextField } from '../../shared/ui/fields'
import { useSaveAction, type DealAction } from './hooks'
import { ACTION_TYPES, type ActionType } from './labels'

interface Props {
  dealId: string
  defaultActor: string
  initial?: DealAction
  onDone: () => void
}

export function ActionForm({ dealId, defaultActor, initial, onDone }: Props) {
  const save = useSaveAction(dealId)
  const [form, setForm] = useState({
    action_type: (initial?.action_type ?? 'meeting') as string,
    title: initial?.title ?? '',
    content: initial?.content ?? '',
    acted_at: toLocalInput(initial?.acted_at ?? new Date().toISOString()),
    actor: initial?.actor ?? defaultActor,
  })
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
      <TextField label="제목" name="title" value={form.title} onChange={set('title')} required />
      <TextArea label="내용" name="content" value={form.content} onChange={set('content')} />
      <TextField label="활동 일시" name="acted_at" type="datetime-local" value={form.acted_at} onChange={set('acted_at')} required />
      <TextField label="활동자" name="actor" value={form.actor} onChange={set('actor')} required />
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
