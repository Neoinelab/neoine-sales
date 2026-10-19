import type { DealDetail } from '../../../shared/model/types'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

interface DealTitleProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** 헤더의 Deal 이름(h1). 쓰기 권한이 있으면 값을 클릭해 그 자리에서 고친다. Deal code·Owner는 Deal 정보 타일에 있다. */
export function DealTitle({ deal, canWrite, onNotice }: DealTitleProps) {
  const { save } = useDealPatch(deal.code, onNotice)

  async function saveName(text: string) {
    const name = text.trim()
    if (name === '') throw new Error('Deal Name을 입력하세요.')
    if (name !== deal.name) await save({ name }, 'Deal 이름이 변경되었습니다.')
  }

  return (
    <div>
      <InlineEdit label="Deal 이름" canEdit={canWrite} asHeading display={deal.name} initial={deal.name} onSave={saveName} />
    </div>
  )
}
