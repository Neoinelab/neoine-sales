import { UserSelect } from '../../../shared/ui/UserSelect'
import { userLabel } from '../../../shared/model/period'
import type { DealDetail } from '../../../shared/model/types'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

interface DealTitleProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 헤더의 Deal 이름(h1)과 Owner. 둘 다 값을 클릭해 그 자리에서 고친다. Deal code는 바꿀 수 없다. */
export function DealTitle({ deal, canWrite, onNotice }: DealTitleProps) {
  const { save } = useDealPatch(deal.code, onNotice)

  async function saveName(text: string) {
    const name = text.trim()
    if (name === '') throw new Error('Deal Name을 입력하세요.')
    if (name !== deal.name) await save({ name }, 'Deal 이름이 변경되었습니다.')
  }

  async function saveOwner(ownerId: string) {
    if (ownerId === '') throw new Error('Owner를 선택하세요.')
    if (ownerId !== deal.ownerId) await save({ ownerId }, 'Owner가 변경되었습니다.')
  }

  return (
    <div>
      <InlineEdit label="Deal 이름" canEdit={canWrite} asHeading display={deal.name} initial={deal.name} onSave={saveName} />
      <p className="dd-meta">
        <span>Deal code: {deal.code}</span>
        <span>
          <InlineEdit
            label="Owner"
            canEdit={canWrite}
            display={`Owner: ${userLabel(deal.owner)}`}
            initial={deal.ownerId}
            kind="custom"
            control={({ value, commit, inputLabel }) => (
              <UserSelect label={inputLabel} name="owner" value={value} onChange={commit} current={deal.owner} />
            )}
            onSave={saveOwner}
          />
        </span>
      </p>
    </div>
  )
}
