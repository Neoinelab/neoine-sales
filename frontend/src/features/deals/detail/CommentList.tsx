import { useState } from 'react'
import { useRemoveComment } from '../../../data/comments'
import type { Query } from '../../../data/result'
import { formatStamp } from '../../../shared/format'
import { canDeleteComment, type Viewer } from '../../../shared/model/permissions'
import { userLabel } from '../../../shared/model/period'
import type { DealComment } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'
import './comments.css'

interface CommentListProps {
  dealCode: string
  comments: Query<DealComment[]>
  me: Viewer | null
  /** 이번 열람에서 읽음 처리된 Comment(Owner에게 "NEW"로 보인다). */
  fresh: ReadonlySet<number>
  /** Comments 탭: 연결된 Action 상자("Action 보기")와 "Deal Comment" 표시를 보인다. */
  onViewAction?: (actionId: number) => void
}

const text = (value: string | null) => (value && value !== '' ? value : '—')

/** Comment 목록(최근순)과 삭제. 읽는 중·빈 상태·읽기 오류를 보이고, 삭제 버튼은 본인 Comment의 sales와 admin에게만 있다. */
export function CommentList({ dealCode, comments, me, fresh, onViewAction }: CommentListProps) {
  const remove = useRemoveComment()
  const [target, setTarget] = useState<DealComment | null>(null)
  const [error, setError] = useState<unknown>(null)
  const items = comments.data ?? []
  const showLinked = onViewAction !== undefined

  async function confirmDelete() {
    if (!target) return
    setError(null)
    try {
      await remove.mutateAsync({ dealCode, commentId: target.id })
    } catch (caught) {
      setError(caught)
    }
    setTarget(null)
  }

  return (
    <div className="cm-wrap">
      <ErrorBanner error={error} format={messageOf} />
      <ErrorBanner error={comments.error} format={messageOf} />
      {comments.isPending && comments.data === undefined && !comments.isError && <p role="status">불러오는 중…</p>}
      {comments.isSuccess && items.length === 0 && !comments.isError && <p className="hint">등록된 Comment가 없습니다.</p>}
      {items.length > 0 && (
        <ul className="cm-list" aria-label="Comment 목록">
          {items.map((c) => (
            <li key={c.id} className="cm-item">
              <div className="cm-head">
                <span>
                  <strong>{userLabel(c.author)}</strong> · {formatStamp(c.createdAt)}
                </span>
                {fresh.has(c.id) ? <span className="cm-mark cm-mark--new">NEW</span> : c.readAt === null && <span className="cm-mark">읽지 않음</span>}
                {me !== null && canDeleteComment(me, c.author.id) && (
                  <button type="button" className="danger dd-small" aria-label="Comment 삭제" onClick={() => setTarget(c)}>
                    삭제
                  </button>
                )}
              </div>
              {showLinked &&
                (c.action ? (
                  <div className="cm-action" role="group" aria-label="연결된 Action">
                    <span>수행일 {c.action.actedOn}</span>
                    <span>진행사항 {text(c.action.progress)}</span>
                    <span>Next Action {text(c.action.nextAction)}</span>
                    <button type="button" className="dd-small" onClick={() => onViewAction(c.actionId ?? 0)}>
                      Action 보기
                    </button>
                  </div>
                ) : (
                  <span className="cm-deal-mark">Deal Comment</span>
                ))}
              <p className="cm-body">{c.body}</p>
            </li>
          ))}
        </ul>
      )}
      {target && (
        <ConfirmDialog
          title="Comment 삭제"
          message="이 Comment를 삭제합니다. 삭제는 Deal History에 기록됩니다."
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setTarget(null)}
        />
      )}
    </div>
  )
}
