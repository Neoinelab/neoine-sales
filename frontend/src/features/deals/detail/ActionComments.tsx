import { useComments } from '../../../data/comments'
import { canMarkCommentsRead, type Viewer } from '../../../shared/model/permissions'
import type { DealAction, DealDetail } from '../../../shared/model/types'
import { CommentComposer } from './CommentComposer'
import { CommentList } from './CommentList'
import { useMarkReadOnOpen } from './useMarkReadOnOpen'
import './comments.css'

interface ActionCommentsProps {
  deal: DealDetail
  action: DealAction
  canWrite: boolean
  me: Viewer | null
  /** 열릴 때 입력 칸에 포커스를 둔다. */
  focusInput: boolean
}

/** Action 상세 팝업의 맨 아래 Comment 영역: 그 Action의 Comment(최근순)와 입력 칸. Deal Owner가 열면 그 Action의 읽지 않던 Comment를 읽음 처리한다. */
export function ActionComments({ deal, action, canWrite, me, focusInput }: ActionCommentsProps) {
  const comments = useComments(deal.code, action.id)
  const fresh = useMarkReadOnOpen(deal.code, comments, me !== null && canMarkCommentsRead(me, deal.ownerId))
  return (
    <section className="cm-section" aria-label="Action Comment">
      <h3>{comments.data ? `Comment (${comments.data.length})` : 'Comment'}</h3>
      <CommentList dealCode={deal.code} comments={comments} me={me} fresh={fresh} />
      {canWrite && <CommentComposer dealCode={deal.code} actionId={action.id} focusOnOpen={focusInput} />}
    </section>
  )
}
