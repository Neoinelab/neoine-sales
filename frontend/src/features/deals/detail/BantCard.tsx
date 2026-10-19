import { useState } from 'react'
import { useCreateLabel, useLabels } from '../../../data/labels'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES, BANT_LABEL_MAX_LENGTH } from '../../../shared/model/constants'
import type { BantCategory, DealDetail } from '../../../shared/model/types'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

interface BantCardProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

const NEW_LABEL = '__new__'

interface BantItemProps extends BantCardProps {
  category: BantCategory
}

/** BANT 항목 하나: 값을 클릭해 Label을 고른다. 맞는 Label이 없으면 '+ 새 Label 만들기'로 즉석 생성(중복은 서버 문구로 거부). */
function BantItem({ deal, canWrite, onNotice, category }: BantItemProps) {
  const labels = useLabels().data ?? []
  const createLabel = useCreateLabel()
  const { save } = useDealPatch(deal.code, onNotice)
  const [newName, setNewName] = useState('')
  const name = BANT_CATEGORY_NAMES[category]
  const options = labels.filter((l) => l.category === category)
  const current = deal.bant[category]
  const selected = options.find((l) => l.id === current)

  async function select(labelId: string | null) {
    if (labelId === current) return
    await save({ bant: { ...deal.bant, [category]: labelId } }, `BANT ${name} Label이 변경되었습니다.`)
  }

  async function saveItem(value: string) {
    if (value !== NEW_LABEL) return select(value === '' ? null : value)
    const label = newName.trim()
    if (label === '') throw new Error('Label 이름을 입력하세요.')
    if (Array.from(label).length > BANT_LABEL_MAX_LENGTH) throw new Error('Label 이름은 50자 이내로 입력하세요.')
    const created = await createLabel.mutateAsync({ category, name: label })
    setNewName('')
    await select(created.id)
  }

  return (
    <div className="kv-row">
      <dt>{name}</dt>
      <dd>
        <InlineEdit
          label={name}
          canEdit={canWrite}
          kind="custom"
          display={selected?.name ?? '—'}
          initial={current ?? ''}
          onSave={saveItem}
          control={({ value, onChange, commit, inputLabel }) => (
            <>
              <select
                aria-label={inputLabel}
                value={value}
                onChange={(e) => {
                  onChange(e.target.value)
                  if (e.target.value !== NEW_LABEL) commit(e.target.value)
                }}
              >
                <option value="">선택 안 함</option>
                {options.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
                <option value={NEW_LABEL}>+ 새 Label 만들기</option>
              </select>
              {value === NEW_LABEL && (
                <input
                  aria-label={`${name} 새 Label 이름`}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  // 새 Label을 고르면 바로 이름을 입력할 수 있게 포커스를 옮긴다.
                  // eslint-disable-next-line jsx-a11y/no-autofocus
                  autoFocus
                />
              )}
            </>
          )}
        />
      </dd>
    </div>
  )
}

/** BANT 4 Label. 쓰기 권한이 있으면 값을 클릭해 그 자리에서 고른다(History 기록). */
export function BantCard({ deal, canWrite, onNotice }: BantCardProps) {
  return (
    <section aria-labelledby="dd-bant" className="dd-card">
      <h2 id="dd-bant">BANT</h2>
      <dl className="kv-grid">
        {BANT_CATEGORIES.map((category) => (
          <BantItem key={category} deal={deal} canWrite={canWrite} onNotice={onNotice} category={category} />
        ))}
      </dl>
    </section>
  )
}
