import { useState } from 'react'
import { useActionTypes, useCreateActionType, useRemoveActionType, useRenameActionType } from '../../../data/actionTypes'
import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { ActionTypeWithUsage } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { InlineNameEdit } from './InlineNameEdit'

/** Action 유형 관리: 목록·추가·이름 수정·삭제. 기본 유형도 이름을 고치거나(사용 중이 아니면) 지울 수 있다. */
export function ActionTypeManager() {
  const types = useActionTypes()
  const create = useCreateActionType()
  const rename = useRenameActionType()
  const remove = useRemoveActionType()
  const [name, setName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<ActionTypeWithUsage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const busy = create.isPending || rename.isPending || remove.isPending

  function add() {
    setError(null)
    create.mutate(name, { onSuccess: () => setName(''), onError: setError })
  }

  function saveName(type: ActionTypeWithUsage, next: string) {
    setError(null)
    rename.mutate({ id: type.id, name: next }, { onSuccess: () => setEditingId(null), onError: setError })
  }

  function confirmDelete(type: ActionTypeWithUsage) {
    setError(null)
    remove.mutate(type.id, { onError: setError, onSettled: () => setDeleting(null) })
  }

  return (
    <div className="admin-page">
      <p className="hint">
        같은 이름은 만들 수 없습니다(대소문자 구분 없음). 사용 중인 유형은 이름을 바꿀 수 있지만 삭제할 수 없습니다.
      </p>
      <ErrorBanner error={error ?? types.error} />
      {types.isPending && <p className="hint">불러오는 중…</p>}
      {types.isSuccess && (
        <section className="admin-card" aria-label="Action 유형">
          <div className="table-wrap">
            <table aria-label="Action 유형 목록">
              <thead>
                <tr>
                  <th>이름</th>
                  <th>사용</th>
                  <th>만든 사용자·시각</th>
                  <th>작업</th>
                </tr>
              </thead>
              <tbody>
                {types.data.map((type) => (
                  <tr key={type.id}>
                    <td>
                      {editingId === type.id ? (
                        <InlineNameEdit
                          label="유형 이름"
                          initial={type.name}
                          busy={busy}
                          onSave={(next) => saveName(type, next)}
                          onCancel={() => setEditingId(null)}
                        />
                      ) : (
                        <>
                          {type.name} {type.isDefault && <span className="badge">기본</span>}
                        </>
                      )}
                    </td>
                    <td className="stat">{`Action ${type.usageCount}건`}</td>
                    <td>{type.createdBy ? `${userLabel(type.createdBy)} · ${formatDateTime(type.createdAt)}` : '시스템'}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          type="button"
                          className="small"
                          disabled={editingId === type.id}
                          onClick={() => {
                            setError(null)
                            setEditingId(type.id)
                          }}
                        >
                          이름 수정
                        </button>
                        <button type="button" className="small" disabled={busy} onClick={() => setDeleting(type)}>
                          삭제
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {types.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="empty">
                      등록된 유형이 없습니다.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <form
            className="admin-form-row"
            aria-label="Action 유형 추가"
            onSubmit={(e) => {
              e.preventDefault()
              add()
            }}
          >
            <TextField label="새 유형 이름" name="new_action_type" value={name} onChange={setName} />
            <button type="submit" className="primary" disabled={busy}>
              추가
            </button>
          </form>
        </section>
      )}
      {deleting && (
        <ConfirmDialog
          title="유형 삭제"
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          message={`'${deleting.name}' 유형을 삭제할까요? 사용 중인 유형은 삭제할 수 없습니다.`}
          onConfirm={() => confirmDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
