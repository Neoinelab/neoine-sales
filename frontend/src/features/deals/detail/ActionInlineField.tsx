import type { ActionUpdateInput } from '../../../shared/model/inputs'
import type { DealAction } from '../../../shared/model/types'
import { dueDatePatch, encodePair, nextActionPatch, progressPatch } from './actionEdit'
import { ActionNextPairInput } from './ActionNextPairInput'
import { ActionTextArea } from './ActionTextArea'
import { InlineEdit } from './InlineEdit'

interface ActionInlineFieldProps {
  action: DealAction
  field: 'progress' | 'nextAction' | 'dueDate'
  canEdit: boolean
  saving: boolean
  onSave: (patch: Partial<ActionUpdateInput>) => Promise<void>
}

export function ActionInlineField({ action, field, canEdit, saving, onSave }: ActionInlineFieldProps) {
  if (field === 'dueDate') {
    return (
      <InlineEdit
        label="Due Date"
        kind="date"
        saveButtons
        otherSaving={saving}
        canEdit={canEdit && Boolean(action.nextAction)}
        display={action.dueDate ?? '—'}
        initial={action.dueDate ?? ''}
        onSave={(value) => onSave(dueDatePatch(action, value))}
      />
    )
  }
  const next = field === 'nextAction'
  return (
    <InlineEdit
      label={next ? 'Next Action · Due Date' : '진행사항'}
      fill
      saveButtons
      otherSaving={saving}
      kind="custom"
      canEdit={canEdit}
      display={action[field] ?? '—'}
      initial={next ? encodePair(action.nextAction ?? '', action.dueDate ?? '') : (action.progress ?? '')}
      control={next ? ActionNextPairInput : ActionTextArea}
      onSave={(value) => onSave(next ? nextActionPatch(action, value) : progressPatch(action, value))}
    />
  )
}
