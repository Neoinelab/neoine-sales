import { useState } from 'react'
import {
  useCreateSolution,
  useCreateVendor,
  useRemoveSolution,
  useRemoveVendor,
  useRenameSolution,
  useRenameVendor,
  useVendors,
} from '../../../data/vendors'
import type { Solution, Vendor } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { VendorCard } from './VendorCard'

type Deleting = { kind: 'vendor'; vendor: Vendor } | { kind: 'solution'; solution: Solution }

function deleteMessage(target: Deleting): string {
  if (target.kind === 'solution') return `'${target.solution.name}' Solution을 삭제할까요?`
  const { name, solutions } = target.vendor
  const tail = solutions.length > 0 ? ` 소속 Solution ${solutions.length}개도 함께 삭제됩니다.` : ''
  return `'${name}' Vendor를 삭제할까요?${tail}`
}

/** Vendor·Solution 관리: Vendor 카드별 Solution 목록, 추가·이름 수정·삭제. 사용 중인 항목의 삭제 거절(409)은 서버 문구를 그대로 보인다. */
export function VendorManager() {
  const vendors = useVendors()
  const createVendor = useCreateVendor()
  const renameVendor = useRenameVendor()
  const removeVendor = useRemoveVendor()
  const createSolution = useCreateSolution()
  const renameSolution = useRenameSolution()
  const removeSolution = useRemoveSolution()
  const [newName, setNewName] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<Deleting | null>(null)
  const [error, setError] = useState<unknown>(null)
  const busy = [createVendor, renameVendor, removeVendor, createSolution, renameSolution, removeSolution].some((m) => m.isPending)
  const deletePending = removeVendor.isPending || removeSolution.isPending

  function addVendor() {
    setError(null)
    createVendor.mutate(newName, { onSuccess: () => setNewName(''), onError: setError })
  }

  function confirmDelete(target: Deleting) {
    setError(null)
    const options = { onError: setError, onSettled: () => setDeleting(null) }
    if (target.kind === 'vendor') removeVendor.mutate(target.vendor.id, options)
    else removeSolution.mutate({ vendorId: target.solution.vendorId, solutionId: target.solution.id }, options)
  }

  return (
    <div className="admin-page">
      <p className="hint">
        Vendor 이름은 대소문자 구분 없이 중복될 수 없고, Solution 이름은 같은 Vendor 안에서 중복될 수 없습니다. 사용 중인 항목은 이름을
        바꿀 수 있지만 삭제할 수 없습니다.
      </p>
      <ErrorBanner error={error ?? vendors.error} />
      {vendors.isPending && <p className="hint">불러오는 중…</p>}
      {vendors.isSuccess && vendors.data.length === 0 && <p className="empty">등록된 Vendor가 없습니다.</p>}
      {vendors.isSuccess &&
        vendors.data.map((vendor) => (
          <VendorCard
            key={vendor.id}
            vendor={vendor}
            editingId={editingId}
            busy={busy}
            onEdit={(id) => {
              setError(null)
              setEditingId(id)
            }}
            onRenameVendor={(v, name) => {
              setError(null)
              renameVendor.mutate({ id: v.id, name }, { onSuccess: () => setEditingId(null), onError: setError })
            }}
            onDeleteVendor={(v) => setDeleting({ kind: 'vendor', vendor: v })}
            onAddSolution={(v, name, done) => {
              setError(null)
              createSolution.mutate({ vendorId: v.id, name }, { onSuccess: done, onError: setError })
            }}
            onRenameSolution={(s, name) => {
              setError(null)
              renameSolution.mutate(
                { vendorId: s.vendorId, solutionId: s.id, name },
                { onSuccess: () => setEditingId(null), onError: setError },
              )
            }}
            onDeleteSolution={(s) => setDeleting({ kind: 'solution', solution: s })}
          />
        ))}
      <form
        className="admin-card"
        aria-label="Vendor 추가"
        onSubmit={(e) => {
          e.preventDefault()
          addVendor()
        }}
      >
        <div className="admin-form-row">
          <TextField label="새 Vendor 이름" name="new_vendor_name" value={newName} onChange={setNewName} />
          <button type="submit" className="primary" disabled={busy}>
            Vendor 추가
          </button>
        </div>
      </form>
      {deleting && (
        <ConfirmDialog
          title={deleting.kind === 'vendor' ? 'Vendor 삭제' : 'Solution 삭제'}
          confirmLabel="삭제"
          danger
          busy={deletePending}
          message={deleteMessage(deleting)}
          onConfirm={() => confirmDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
