import { useState } from 'react'
import { useRemoveMeeting } from '../../data/partnerMeetings'
import type { PartnerMeeting } from '../../shared/model/types'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'

interface MeetingDeleteDialogProps {
  meeting: PartnerMeeting
  onClose: () => void
}

export function MeetingDeleteDialog({ meeting, onClose }: MeetingDeleteDialogProps) {
  const remove = useRemoveMeeting()
  const [error, setError] = useState<unknown>(null)

  async function confirm() {
    setError(null)
    try {
      await remove.mutateAsync(meeting.id)
      onClose()
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <ConfirmDialog title="미팅 기록 삭제" message="이 미팅 기록을 삭제할까요?" confirmLabel="삭제" danger busy={remove.isPending} onConfirm={() => void confirm()} onCancel={onClose}>
      <ErrorBanner error={error} />
    </ConfirmDialog>
  )
}
