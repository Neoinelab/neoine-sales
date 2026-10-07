import { useState } from 'react'
import { Link } from 'react-router'
import { PAGE_SIZE } from '../../shared/constants'
import { formatDateTime } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Pager } from '../../shared/ui/Pager'
import { useMe } from '../auth/hooks'
import { ActionFilterBar } from './ActionFilterBar'
import { ActionForm } from './ActionForm'
import { useActions, useDeleteAction, type ActionFilters, type DealAction } from './hooks'
import { actionLabel } from './labels'

interface Props {
  /** 있으면 그 딜의 이력(기록·수정·삭제 가능), 없으면 전체 활동 검색(조회 전용). */
  dealId?: string
}

type Editing = { kind: 'new' } | { kind: 'edit'; action: DealAction } | null

export function ActionList({ dealId }: Props) {
  const me = useMe()
  const [filters, setFilters] = useState<ActionFilters>({})
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<Editing>(null)
  const actions = useActions(dealId, filters, offset)
  const remove = useDeleteAction()
  const items = actions.data?.items ?? []

  return (
    <section aria-label="활동 이력">
      <div className="heading">
        <h2>활동 이력</h2>
        {dealId && (
          <button type="button" className="primary" onClick={() => setEditing({ kind: 'new' })}>
            활동 기록
          </button>
        )}
      </div>
      <ActionFilterBar
        onSearch={(next) => {
          setFilters(next)
          setOffset(0)
        }}
      />
      <ErrorBanner error={actions.error ?? remove.error} />
      {dealId && editing && (
        <ActionForm
          key={editing.kind === 'edit' ? editing.action.id : 'new'}
          dealId={dealId}
          defaultActor={me.data?.name ?? ''}
          initial={editing.kind === 'edit' ? editing.action : undefined}
          onDone={() => setEditing(null)}
        />
      )}
      <table>
        <thead>
          <tr>
            <th>일시</th>
            <th>유형</th>
            <th>제목</th>
            <th>내용</th>
            <th>활동자</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id}>
              <td>{formatDateTime(a.acted_at)}</td>
              <td>{actionLabel(a.action_type)}</td>
              <td>{a.title}</td>
              <td className="wrap">{a.content}</td>
              <td>{a.actor}</td>
              <td className="row-actions">
                {dealId ? (
                  <>
                    <button type="button" onClick={() => setEditing({ kind: 'edit', action: a })}>
                      수정
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`'${a.title}' 활동을 삭제할까요?`)) remove.mutate(a.id)
                      }}
                    >
                      삭제
                    </button>
                  </>
                ) : (
                  <Link to={`/deals/${a.deal_id}`}>딜 보기</Link>
                )}
              </td>
            </tr>
          ))}
          {actions.isSuccess && items.length === 0 && (
            <tr>
              <td colSpan={6}>조건에 맞는 활동이 없습니다.</td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager offset={offset} limit={PAGE_SIZE} count={items.length} onChange={setOffset} />
    </section>
  )
}
