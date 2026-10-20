import { Notice } from '../ui/Notice'

interface SyncNoticeProps {
  /** SyncApplied.notice. 배열이면 null을 뺀 문장을 이어 보인다. 보일 문장이 없으면 아무것도 그리지 않는다. */
  notice: string | null | ReadonlyArray<string | null>
  /** 폼 draft에 반영만 한 상태(저장 전)면 true: "...함께 변경됩니다. 저장하면 반영됩니다." (안내는 한 번만) */
  draft?: boolean
  onClose?: () => void
}

/** "함께 바뀐 값" 알림(role=status, 닫기 가능). */
export function SyncNotice({ notice, draft = false, onClose }: SyncNoticeProps) {
  const sentences = (typeof notice === 'string' || notice === null ? [notice] : notice).filter((s): s is string => !!s)
  if (sentences.length === 0) return null
  const body = sentences.map((s) => (draft ? s.replace(/되었습니다\.$/, '됩니다.') : s)).join(' ')
  return (
    <Notice kind="info" onClose={onClose}>
      {draft ? `${body} 저장하면 반영됩니다.` : body}
    </Notice>
  )
}
