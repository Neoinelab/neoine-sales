import { Notice } from '../ui/Notice'

interface SyncNoticeProps {
  /** SyncApplied.notice. null이면 아무것도 그리지 않는다. */
  notice: string | null
  /** 폼 draft에 반영만 한 상태(저장 전)면 true: "...함께 변경됩니다. 저장하면 반영됩니다." */
  draft?: boolean
  onClose?: () => void
}

/** "함께 바뀐 값" 알림(role=status, 닫기 가능). */
export function SyncNotice({ notice, draft = false, onClose }: SyncNoticeProps) {
  if (!notice) return null
  const text = draft ? `${notice.replace(/되었습니다\.$/, '됩니다.')} 저장하면 반영됩니다.` : notice
  return (
    <Notice kind="info" onClose={onClose}>
      {text}
    </Notice>
  )
}
