import { useState } from 'react'
import { useLabels } from '../../../data/labels'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES, type BantCategory } from '../../../shared/model/constants'
import { SelectField } from '../../../shared/ui/fields'
import { NewLabelInput } from './NewLabelInput'
import type { SectionProps } from './sectionTypes'

/**
 * ⑥ BANT: 항목마다 Label 하나(선택 안 함 포함). 맞는 Label이 없으면 `+ 새 Label`로 그 자리에서 만든다.
 * 기존 Label의 이름 수정·삭제는 이 화면에 없다(Admin > Deal 관리).
 */
export function BantSection({ state, set }: SectionProps) {
  const labels = useLabels().data ?? []
  const [creating, setCreating] = useState<BantCategory | null>(null)

  function select(category: BantCategory, id: string) {
    set('bant', { ...state.bant, [category]: id === '' ? null : id })
  }

  return (
    <section className="form-section" aria-labelledby="sec-bant">
      <h2 id="sec-bant">BANT</h2>
      <fieldset className="bant-fieldset">
        <legend className="kv-visually-hidden">BANT</legend>
        <div className="kv-grid">
          {BANT_CATEGORIES.map((category) => {
            const title = BANT_CATEGORY_NAMES[category]
            return (
              <div key={category} className="kv-row">
                <SelectField label={title} name={`bant-${category}`} value={state.bant[category] ?? ''} onChange={(id) => select(category, id)}>
                  <option value="">선택 안 함</option>
                  {labels
                    .filter((l) => l.category === category)
                    .map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.name}
                      </option>
                    ))}
                </SelectField>
                {creating === category ? (
                  <NewLabelInput
                    category={category}
                    onCancel={() => setCreating(null)}
                    onCreated={(id) => {
                      select(category, id)
                      setCreating(null)
                    }}
                  />
                ) : (
                  <button type="button" className="link-button" aria-label={`${title} 새 Label`} onClick={() => setCreating(category)}>
                    + 새 Label
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </fieldset>
    </section>
  )
}
