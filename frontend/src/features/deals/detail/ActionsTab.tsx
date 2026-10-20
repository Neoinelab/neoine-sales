import { useState } from 'react'
import { useActions, useChangeNextActionStatus, useRemoveAction } from '../../../data/actions'
import type { Viewer } from '../../../shared/model/permissions'
import type { ActionQuery, DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { ActionForm } from './ActionForm'
import { ActionSearchBar } from './ActionSearchBar'
import { ActionTable } from './ActionTable'
import { messageOf } from './detailHelpers'
import { NextActionCloseDialog } from './NextActionCloseDialog'
import { useLatest } from './useLatest'
import './detail.css'

interface ActionsTabProps {
  deal: DealDetail
  canWrite: boolean
  me: Viewer | null
  onNotice: (message: string) => void
}

type FormState = { mode: 'closed' } | { mode: 'create' } | { mode: 'edit'; action: DealAction }

/** Actions 탭: 검색 + 목록 + Next Action 업데이트 폼(등록·수정) + 삭제 확인. */
export function ActionsTab({ deal, canWrite, me, onNotice }: ActionsTabProps) {
  const [query, setQuery] = useState<ActionQuery>({})
  const [form, setForm] = useState<FormState>({ mode: 'closed' })
  const [target, setTarget] = useState<DealAction | null>(null)
  const [closing, setClosing] = useState<{ action: DealAction; status: Exclude<NextActionStatus, 'open'> } | null>(null)
  const [closingError, setClosingError] = useState<unknown>(null)
  const [error, setError] = useState<unknown>(null)
  const list = useActions(deal.code, query)
  const all = useActions(deal.code)
  const remove = useRemoveAction()
  const changeStatus = useChangeNextActionStatus()
  const items = useLatest(list.data) ?? []
  const filtered = Object.keys(query).some((k) => k !== 'sort') || (query.sort !== undefined && query.sort !== 'actedDesc')

  async function confirmDelete() {
    if (!target) return
    setError(null)
    try {
      await remove.mutateAsync({ dealCode: deal.code, actionId: target.id })
      onNotice('Action이 삭제되었습니다.')
    } catch (caught) {
      setError(caught)
    }
    setTarget(null)
  }

  /** 성공하면 true. 실패하면 오류를 보이고 팝업과 입력한 Memo를 그대로 둔다. */
  async function setStatus(action: DealAction, status: NextActionStatus, memo: string): Promise<boolean> {
    setError(null)
    setClosingError(null)
    try {
      await changeStatus.mutateAsync({ dealCode: deal.code, actionId: action.id, input: { status, memo } })
      return true
    } catch (caught) {
      if (status === 'open') setError(caught)
      else setClosingError(caught)
      return false
    }
  }

  async function confirmClose(memo: string) {
    if (closing && (await setStatus(closing.action, closing.status, memo))) setClosing(null)
  }

  function cancelClose() {
    setClosing(null)
    setClosingError(null)
  }

  /** 종료는 Memo 팝업을 거치고, Open으로 되돌리는 것은 팝업 없이 바로 바꾼다. */
  function requestStatus(action: DealAction, status: NextActionStatus) {
    if (status === 'open') void setStatus(action, status, '')
    else {
      setClosingError(null)
      setClosing({ action, status })
    }
  }

  function done(message: string) {
    setForm({ mode: 'closed' })
    onNotice(message)
  }

  return (
    <div className="dd-page">
      {canWrite && form.mode === 'closed' && (
        <div className="dd-row">
          <button type="button" className="primary" onClick={() => setForm({ mode: 'create' })}>
            Next Action 업데이트
          </button>
        </div>
      )}
      {form.mode !== 'closed' && (
        <ActionForm
          key={form.mode === 'edit' ? form.action.id : 'create'}
          deal={deal}
          editing={form.mode === 'edit' ? form.action : null}
          previous={all.data?.find((a) => a.nextAction !== null) ?? null}
          onDone={done}
          onCancel={() => setForm({ mode: 'closed' })}
        />
      )}
      <ActionSearchBar onSearch={setQuery} />
      <ErrorBanner error={error} format={messageOf} />
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
          onEdit={(action) => setForm({ mode: 'edit', action })}
          onDelete={setTarget}
          onChangeStatus={requestStatus}
          statusBusy={changeStatus.isPending}
        />
      )}
      {closing && (
        <NextActionCloseDialog
          status={closing.status}
          nextAction={closing.action.nextAction ?? ''}
          busy={changeStatus.isPending}
          error={closingError}
          onConfirm={(memo) => void confirmClose(memo)}
          onCancel={cancelClose}
        />
      )}
      {target && (
        <ConfirmDialog
          title="Action 삭제"
          message={`"${target.progress ?? target.nextAction ?? ''}" Action을 삭제합니다. 삭제는 Deal History에 기록됩니다.`}
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
