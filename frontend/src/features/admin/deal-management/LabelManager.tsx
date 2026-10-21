import { useState } from 'react'
import { useCreateLabel, useLabels, useRemoveLabel, useRenameLabel } from '../../../data/labels'
import { BANT_CATEGORIES, type BantCategory } from '../../../shared/model/constants'
import type { BantLabelWithUsage } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { LabelCategoryCard } from './LabelCategoryCard'

/** BANT Label 관리: 구분(Budget/Authority/Need/Timeline)별 목록·추가·이름 수정·삭제. 기본 Label도 이름을 고칠 수 있다. */
export function LabelManager() {
  const labels = useLabels()
  const create = useCreateLabel()
  const rename = useRenameLabel()
  const remove = useRemoveLabel()
  const [editingId, setEditingId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<BantLabelWithUsage | null>(null)
  const [error, setError] = useState<unknown>(null)
  const busy = create.isPending || rename.isPending || remove.isPending

  function add(category: BantCategory, name: string, done: () => void) {
    setError(null)
    create.mutate({ category, name }, { onSuccess: done, onError: setError })
  }

  function saveName(label: BantLabelWithUsage, name: string) {
    setError(null)
    rename.mutate({ id: label.id, name }, { onSuccess: () => setEditingId(null), onError: setError })
  }

  function confirmDelete(label: BantLabelWithUsage) {
    setError(null)
    remove.mutate(label.id, { onError: setError, onSettled: () => setDeleting(null) })
  }

  return (
    <div className="admin-page">
      <p className="hint">
        구분마다 같은 이름은 만들 수 없습니다(대소문자 구분 없음). 사용 중인 Label은 이름을 바꿀 수 있지만 삭제할 수 없습니다.
      </p>
      <ErrorBanner error={error ?? labels.error} />
      {labels.isPending && <p className="hint">불러오는 중…</p>}
      {labels.isSuccess && (
        <div className="label-columns">
          {BANT_CATEGORIES.map((category) => (
            <LabelCategoryCard
              key={category}
              category={category}
              labels={labels.data.filter((l) => l.category === category)}
              editingId={editingId}
              busy={busy}
              onAdd={(name, done) => add(category, name, done)}
              onEdit={(id) => {
                setError(null)
                setEditingId(id)
              }}
              onRename={saveName}
              onDelete={setDeleting}
            />
          ))}
        </div>
      )}
      {deleting && (
        <ConfirmDialog
          title="Label 삭제"
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          message={`'${deleting.name}' Label을 삭제할까요? 사용 중인 Label은 삭제할 수 없습니다.`}
          onConfirm={() => confirmDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
