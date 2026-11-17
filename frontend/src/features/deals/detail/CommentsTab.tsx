import { useComments } from '../../../data/comments'
import { canMarkCommentsRead, type Viewer } from '../../../shared/model/permissions'
import type { DealDetail } from '../../../shared/model/types'
import { CommentComposer } from './CommentComposer'
import { CommentList } from './CommentList'
import { useMarkReadOnOpen } from './useMarkReadOnOpen'
import './comments.css'

interface CommentsTabProps {
  deal: DealDetail
  canWrite: boolean
  me: Viewer | null
  /** "Action 보기": Actions 탭에서 그 Action의 상세 팝업을 연다. */
  onViewAction: (actionId: number) => void
}

/** Comments 탭: Deal의 모든 Comment(최근순)와 아래 입력 칸. Deal Owner가 열면 읽지 않던 Comment를 읽음 처리한다. */
export function CommentsTab({ deal, canWrite, me, onViewAction }: CommentsTabProps) {
  const comments = useComments(deal.code)
  const fresh = useMarkReadOnOpen(deal.code, comments, me !== null && canMarkCommentsRead(me, deal.ownerId))
  return (
    <div className="dd-page cm-section">
      <CommentList dealCode={deal.code} comments={comments} me={me} fresh={fresh} onViewAction={onViewAction} />
      {canWrite && <CommentComposer dealCode={deal.code} />}
    </div>
  )
}
