import { badgeText } from '../model/commentBadge'

/** 읽지 않은 Comment 수 배지(링크·버튼 아님). 0건이면 그리지 않는다. 표기는 `badgeText`(100건 이상 "99+"). */
export function CommentBadge({ count }: { count: number }) {
  const text = badgeText(count)
  if (text === null) return null
  const label = `읽지 않은 Comment ${count}건`
  return (
    <span className="comment-badge" role="img" aria-label={label} title={label}>
      {text}
    </span>
  )
}
