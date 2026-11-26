import { useState } from 'react'
import { useActions, useChangeNextActionStatus, useRemoveAction, useUpdateAction } from '../../../data/actions'
import type { ActionUpdateInput } from '../../../shared/model/inputs'
import { updateBody } from './actionEdit'
import { useCommentCounts, useComments } from '../../../data/comments'
import type { Viewer } from '../../../shared/model/permissions'
import type { ActionQuery, DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { ActionDetailDialog } from './ActionDetailDialog'
import { ActionForm } from './ActionForm'
import { ActionSearchBar } from './ActionSearchBar'
import { DEFAULT_ACTION_SORT, nextActionSort, type ActionSortState } from './actionSort'
import { ActionTable } from './ActionTable'
import { useActionDeepLink } from './useActionDeepLink'
import { messageOf } from './detailHelpers'
import { NextActionStatusDialog } from './NextActionStatusDialog'
import { useLatest } from './useLatest'
import './detail.css'

interface ActionsTabProps {
  deal: DealDetail
  canWrite: boolean
  me: Viewer | null
  onNotice: (message: string) => void
}

/** Actions 탭: 검색 + 목록 + Action 추가 팝업 + 행을 눌러 여는 Action 상세 팝업(칸별 수정·상태 변경·삭제) + 삭제 확인. */
export function ActionsTab({ deal, canWrite, me, onNotice }: ActionsTabProps) {
  const [query, setQuery] = useState<ActionQuery>({})
  // 정렬은 검색 조건과 따로 둔다(초기화해도 유지, 조건 없음 판정에도 포함하지 않는다).
  const [sort, setSort] = useState<ActionSortState>(DEFAULT_ACTION_SORT)
  const [creating, setCreating] = useState(false)
  // 상세 팝업: 연 Action(목록에서 사라져도 마지막 값으로 남는다)과 지금 값(수정·종료가 반영된 목록).
  const [opened, setOpened] = useState<DealAction | null>(null)
  // 표의 Comment 아이콘으로 열었으면 팝업이 Comment 입력 칸에 포커스를 둔다.
  const [focusComment, setFocusComment] = useState(false)
  const [target, setTarget] = useState<DealAction | null>(null)
  const [statusTarget, setStatusTarget] = useState<{ action: DealAction; status: NextActionStatus } | null>(null)
  const [statusError, setStatusError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const list = useActions(deal.code, { ...query, ...sort })
  // 기본 정렬로 조회해 조건 없는 목록과 쿼리 키를 맞춘다(같은 GET을 두 번 보내지 않는다).
  const all = useActions(deal.code, DEFAULT_ACTION_SORT)
  const remove = useRemoveAction()
  const update = useUpdateAction()
  const changeStatus = useChangeNextActionStatus()
  const commentCounts = useCommentCounts(deal.code)
  // Comments 탭의 "Action 보기"로 들어오면(주소 `action`) 그 Action의 상세 팝업을 연다.
  const linkError = useActionDeepLink(all, (action) => {
    setError(null)
    setFocusComment(false)
    setOpened(action)
  })
  // 삭제 확인 문구의 건수. 팝업이 이미 읽은 그 Action의 Comment 목록을 같은 키로 쓴다.
  const targetComments = useComments(target ? deal.code : undefined, target?.id ?? null)
  const items = useLatest(list.data) ?? []
  // 기준 행은 서버가 정한 `deal.nextAction.actionId`의 행이다(화면에서 다시 계산하지 않는다).
  const basis = deal.nextAction === null ? null : (all.data?.find((a) => a.id === deal.nextAction?.actionId) ?? null)
  const filtered = Object.keys(query).length > 0
  const shown = opened === null ? null : (all.data?.find((a) => a.id === opened.id) ?? opened)

  async function confirmDelete() {
    if (!target) return
    setError(null)
    try {
      await remove.mutateAsync({ dealCode: deal.code, actionId: target.id })
      setOpened(null)
      onNotice('Action이 삭제되었습니다.')
    } catch (caught) {
      setError(caught)
    }
    setTarget(null)
  }

  async function confirmStatus(comment: string) {
    if (!statusTarget) return
    const { action, status } = statusTarget
    setError(null)
    setStatusError(null)
    try {
      await changeStatus.mutateAsync({ dealCode: deal.code, actionId: action.id, input: { status, comment } })
      setStatusTarget(null)
    } catch (caught) {
      setStatusError(caught)
    }
  }

  function cancelStatus() {
    setStatusTarget(null)
    setStatusError(null)
  }

  function requestStatus(action: DealAction, status: NextActionStatus) {
    setStatusError(null)
    setStatusTarget({ action, status })
  }

  function done(message: string) {
    setCreating(false)
    onNotice(message)
  }

  async function save(action: DealAction, patch: Partial<ActionUpdateInput>) {
    await update.mutateAsync({ dealCode: deal.code, actionId: action.id, input: updateBody(action, patch) })
    onNotice('Action이 수정되었습니다.')
  }

  const linkedComments = targetComments.data?.length ?? 0
  const commentNote = linkedComments > 0 ? ` 연결된 Comment ${linkedComments}건도 함께 삭제됩니다.` : ''

  return (
    <div className="dd-page">
      {creating && (
        <ActionForm deal={deal} previous={basis} onDone={done} onCancel={() => setCreating(false)} />
      )}
      <ActionSearchBar onSearch={setQuery} onCreate={canWrite ? () => setCreating(true) : undefined} />
      {shown === null && <ErrorBanner error={error} format={messageOf} />}
      <ErrorBanner error={linkError} format={String} />
      <ErrorBanner error={list.error} format={messageOf} />
      {list.isPending && list.data === undefined && items.length === 0 && <p role="status">불러오는 중…</p>}
      {list.isSuccess && items.length === 0 && (
        <p className="hint">{filtered ? '조건에 맞는 Action이 없습니다.' : '등록된 Action이 없습니다.'}</p>
      )}
      {items.length > 0 && (
        <ActionTable
          actions={items}
          deal={deal}
          canEdit={canWrite}
          me={me}
          sort={sort}
          onSort={(key) => setSort((current) => nextActionSort(current, key))}
          onOpen={(action) => {
            setError(null)
            setFocusComment(false)
            setOpened(action)
          }}
          commentCounts={commentCounts.data?.byAction}
          onOpenComment={(action) => {
            setError(null)
            setFocusComment(true)
            setOpened(action)
          }}
          onChangeStatus={requestStatus}
          statusBusy={changeStatus.isPending || update.isPending}
          onSave={save}
          saving={update.isPending}
        />
      )}
      {shown && (
        <ActionDetailDialog
          deal={deal}
          action={shown}
          canWrite={canWrite}
          me={me}
          pending={changeStatus.isPending || remove.isPending}
          error={error}
          onChangeStatus={requestStatus}
          onDelete={setTarget}
          onNotice={onNotice}
          focusComment={focusComment}
          onClose={() => setOpened(null)}
        />
      )}
      {statusTarget && (
        <NextActionStatusDialog
          status={statusTarget.status}
          nextAction={statusTarget.action.nextAction ?? ''}
          busy={changeStatus.isPending}
          error={statusError}
          onConfirm={(comment) => void confirmStatus(comment)}
          onCancel={cancelStatus}
        />
      )}
      {target && (
        <ConfirmDialog
          title="Action 삭제"
          message={`"${target.progress ?? target.nextAction ?? ''}" Action을 삭제합니다. 삭제는 Deal History에 기록됩니다.${commentNote}`}
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
