import { useState } from 'react'
import { useCodes, useCreateCode, useRemoveCode, useRenameCode, useReorderCodes } from '../../../data/codes'
import type { CodeKind, CodeWithUsage } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { CodeRow } from './CodeRow'

const TITLES: Record<CodeKind, string> = { status: 'Status 코드', forecast: 'Forecast 코드' }

/** Status 또는 Forecast 코드 관리: 목록(순서·이름·내부 key·사용 건수), 추가, 이름·순서 수정, 삭제. */
export function CodeManager({ kind }: { kind: CodeKind }) {
  const codes = useCodes(kind)
  const create = useCreateCode()
  const rename = useRenameCode()
  const reorder = useReorderCodes()
  const remove = useRemoveCode()
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<CodeWithUsage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const list = codes.data ?? []
  const busy = create.isPending || rename.isPending || reorder.isPending || remove.isPending

  function add() {
    setError(null)
    create.mutate({ kind, name: newName }, { onSuccess: () => setNewName(''), onError: setError })
  }

  function saveName(code: CodeWithUsage, name: string) {
    setError(null)
    rename.mutate({ id: code.id, name }, { onSuccess: () => setEditingId(null), onError: setError })
  }

  function move(index: number, direction: -1 | 1) {
    const ids = list.map((c) => c.id)
    const target = index + direction
    const a = ids[index]
    const b = ids[target]
    if (a === undefined || b === undefined) return
    ids[index] = b
    ids[target] = a
    setError(null)
    reorder.mutate({ kind, orderedIds: ids }, { onError: setError })
  }

  function confirmDelete(code: CodeWithUsage) {
    setError(null)
    remove.mutate(code.id, { onError: setError, onSettled: () => setDeleting(null) })
  }

  const forecast = kind === 'forecast'
  return (
    <div className="admin-page">
      <p className="hint">Won과 계약완료는 이름을 바꿔도 같은 의미로 동기화됩니다(CM-07). 이름과 순서를 바꾸면 목록·상세·필터에 바로 반영됩니다.</p>
      <ErrorBanner error={error ?? codes.error} />
      {codes.isPending && <p className="hint">불러오는 중…</p>}
      {codes.isSuccess && (
        <div className="table-wrap">
          <table aria-label={TITLES[kind]}>
            <thead>
              <tr>
                <th>순서</th>
                <th>이름</th>
                <th>내부 코드</th>
                {forecast && <th>확률 참고</th>}
                {forecast && <th>구분</th>}
                <th>사용 중 Deal</th>
                <th>시스템</th>
                <th>작업</th>
              </tr>
            </thead>
            <tbody>
              {list.map((code, index) => (
                <CodeRow
                  key={code.id}
                  code={code}
                  isFirst={index === 0}
                  isLast={index === list.length - 1}
                  editing={editingId === code.id}
                  busy={busy}
                  onEdit={() => {
                    setError(null)
                    setEditingId(code.id)
                  }}
                  onSaveName={(name) => saveName(code, name)}
                  onCancelEdit={() => setEditingId(null)}
                  onMove={(d) => move(index, d)}
                  onDelete={() => setDeleting(code)}
                />
              ))}
              {list.length === 0 && (
                <tr>
                  <td colSpan={forecast ? 8 : 6} className="empty">
                    등록된 코드가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <form
        className="admin-card"
        aria-label={`${TITLES[kind]} 추가`}
        onSubmit={(e) => {
          e.preventDefault()
          add()
        }}
      >
        <div className="admin-form-row">
          <TextField label="새 코드 이름" name="new_code_name" value={newName} onChange={setNewName} />
          <button type="submit" className="primary" disabled={create.isPending}>
            추가
          </button>
        </div>
        <p className="hint">내부 코드는 이름에서 자동으로 만들어지며 한 번 만들면 바뀌지 않습니다.</p>
      </form>
      {deleting && (
        <ConfirmDialog
          title="코드 삭제"
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          message={`'${deleting.name}' 코드를 삭제할까요? 사용 중인 코드는 삭제할 수 없습니다.`}
          onConfirm={() => confirmDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
