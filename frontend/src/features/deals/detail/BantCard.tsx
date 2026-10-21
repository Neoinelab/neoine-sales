import { useLabels } from '../../../data/labels'
import { toChoice, type CatalogChoice } from '../../../shared/model/catalogChoice'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from '../../../shared/model/constants'
import type { BantCategory, DealDetail } from '../../../shared/model/types'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

interface BantCardProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

interface BantItemProps extends BantCardProps {
  category: BantCategory
}

/** 현재 선택을 선택 객체로 옮긴다(바꾸지 않는 구분은 그대로 보낸다). */
const currentChoice = (labelId: number | null): CatalogChoice | null => (labelId === null ? null : { id: labelId })

/**
 * BANT 항목 하나: 값을 클릭하면 자동완성 입력이 열린다.
 * 후보를 고르면 바로 저장하고, 직접 입력한 이름은 Enter·포커스 이동에 저장한다(없는 이름은 서버가 새 Label로 만든다). 비우면 선택 안 함.
 */
function BantItem({ deal, canWrite, onNotice, category }: BantItemProps) {
  const labels = useLabels().data ?? []
  const { save } = useDealPatch(deal.code, onNotice)
  const name = BANT_CATEGORY_NAMES[category]
  const labelsOfCategory = labels.filter((l) => l.category === category)
  const current = deal.bant[category]
  const selected = labelsOfCategory.find((l) => l.id === current)

  async function saveItem(text: string, option?: { id?: number }) {
    const choice: CatalogChoice | null = option?.id !== undefined ? { id: option.id } : toChoice(text, labelsOfCategory)
    if (choice === null ? current === null : 'id' in choice && choice.id === current) return
    const bant = Object.fromEntries(
      BANT_CATEGORIES.map((c) => [c, c === category ? choice : currentChoice(deal.bant[c])]),
    ) as Record<BantCategory, CatalogChoice | null>
    await save({ bant }, `BANT ${name} Label이 변경되었습니다.`)
  }

  return (
    <div className="kv-row">
      <dt>{name}</dt>
      <dd>
        <InlineEdit
          label={name}
          canEdit={canWrite}
          kind="combo"
          display={selected?.name ?? '—'}
          initial={selected?.name ?? ''}
          options={labelsOfCategory.map((l) => ({ value: l.name, id: l.id }))}
          onSave={saveItem}
        />
      </dd>
    </div>
  )
}

/** BANT 4 Label. 쓰기 권한이 있으면 값을 클릭해 그 자리에서 고르거나 입력한다(History 기록). */
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
