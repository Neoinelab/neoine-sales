import { userLabel } from '../../../shared/model/period'
import type { DealDetail } from '../../../shared/model/types'
import { UserSelect } from '../../../shared/ui/UserSelect'
import { InlineEdit } from './InlineEdit'
import { useDealPatch } from './useDealPatch'

interface DealIdentityRowsProps {
  deal: DealDetail
  canWrite: boolean
  onNotice: (message: string) => void
}

/** Deal 정보 타일 맨 앞의 Deal code(읽기 전용)와 Owner(쓰기 권한이 있으면 값을 클릭해 그 자리에서 고침). */
export function DealIdentityRows({ deal, canWrite, onNotice }: DealIdentityRowsProps) {
  const { save } = useDealPatch(deal.code, onNotice)

  async function saveOwner(ownerId: string) {
    if (ownerId === '') throw new Error('Owner를 선택하세요.')
    if (ownerId !== deal.ownerId) await save({ ownerId }, 'Owner가 변경되었습니다.')
  }

  return (
    <>
      <div className="kv-row">
        <dt>Deal code</dt>
        <dd>
          <span className="kv-static">{deal.code}</span>
        </dd>
      </div>
      <div className="kv-row">
        <dt>Owner</dt>
        <dd>
          <InlineEdit
            label="Owner"
            canEdit={canWrite}
            display={userLabel(deal.owner)}
            initial={deal.ownerId}
            kind="custom"
            control={({ value, commit, inputLabel }) => (
              <UserSelect label={inputLabel} name="owner" value={value} onChange={commit} current={deal.owner} />
            )}
            onSave={saveOwner}
          />
        </dd>
      </div>
    </>
  )
}
