import { useState } from 'react'
import { useActions, useRemoveAction } from '../../../data/actions'
import type { Viewer } from '../../../shared/model/permissions'
import type { ActionQuery, DealAction, DealDetail } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { ActionForm } from './ActionForm'
import { ActionSearchBar } from './ActionSearchBar'
import { ActionTable } from './ActionTable'
import { messageOf } from './detailHelpers'
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
  const [error, setError] = useState<unknown>(null)
  const list = useActions(deal.code, query)
  const all = useActions(deal.code)
  const remove = useRemoveAction()
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
          previous={all.data?.[0] ?? null}
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
        />
      )}
      {target && (
        <ConfirmDialog
          title="Action 삭제"
          message={`"${target.progress}" Action을 삭제합니다. 삭제는 Deal History에 기록됩니다.`}
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
