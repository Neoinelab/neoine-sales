import { useUpdateActionDueDate } from '../../../data/actions'
import type { NextActionSummary } from '../../../shared/model/types'
import { InlineEdit } from '../detail/InlineEdit'

interface NextActionDueDateProps {
  dealCode: string
  next: NextActionSummary
  canWrite: boolean
  onSaved: (message: string) => void
}

export function NextActionDueDate({ dealCode, next, canWrite, onSaved }: NextActionDueDateProps) {
  const update = useUpdateActionDueDate()
  return (
    <div className="inline-editor">
      <InlineEdit
        label="Due Date"
        kind="date"
        canEdit={canWrite}
        saveButtons
        otherSaving={update.isPending}
        display={next.dueDate}
        initial={next.dueDate}
        onSave={async (dueDate) => {
          if (dueDate === '') throw new Error('Due Date를 입력하세요.')
          await update.mutateAsync({ dealCode, actionId: next.actionId, dueDate })
          onSaved('Due Date가 변경되었습니다.')
        }}
      />
    </div>
  )
}
