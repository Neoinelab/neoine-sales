import type { ActionUpdateInput } from '../../../shared/model/inputs'
import type { NextActionStatus, DealAction } from '../../../shared/model/types'
import { ForecastBadge, StatusBadge } from '../../../shared/ui/Badges'
import { userLabel } from '../../../shared/model/period'
import { ActionNextPairInput } from './ActionNextPairInput'
import { ActionTextArea } from './ActionTextArea'
import { ActionTypeInput } from './ActionTypeInput'
import { actedOnPatch, encodePair, nextActionPatch, progressPatch, typePatch } from './actionEdit'
import { InlineEdit } from './InlineEdit'
import { NextActionStatusCell } from './NextActionStatusCell'

interface ActionDetailFieldsProps {
  action: DealAction
  /** 칸을 고칠 수 있는 사람(본인 Action의 작성자·admin)인지. */
  canEdit: boolean
  today: string
  registeredOn: string
  types: readonly { id: number; name: string }[]
  statusBusy: boolean
  /** 이 팝업의 칸 저장이 진행 중이다(다른 칸의 "저장"을 끈다). */
  saving: boolean
  onChangeStatus: (action: DealAction, status: NextActionStatus) => void
  /** 바꾼 칸만 담아 저장한다. 화면 검증 위반은 Error로 reject한다. */
  onSave: (patch: Partial<ActionUpdateInput>) => Promise<void>
}

/** Action 상세 팝업의 항목 목록: 칸마다 값을 누르면 그 자리에서 고친다(담당자·등록 시점 Status·Forecast·상태는 고치지 않는다). */
export function ActionDetailFields({ action, canEdit, today, registeredOn, types, statusBusy, saving, onChangeStatus, onSave }: ActionDetailFieldsProps) {
  const text = (value: string | null) => (value && value !== '' ? value : '—')
  return (
    <dl className="dd-dl dd-action-dl">
      <dt>수행일</dt>
      <dd>
        <InlineEdit
          label="수행일"
          kind="date"
          canEdit={canEdit}
          display={action.actedOn}
          initial={action.actedOn}
          onSave={(value) => onSave(actedOnPatch(value, today, registeredOn))}
        />
      </dd>
      <dt>담당자</dt>
      <dd>{userLabel(action.actor)}</dd>
      <dt>등록 시점 Status·Forecast</dt>
      <dd>
        <span className="dd-row">
          <StatusBadge statusKey={action.statusKey} />
          <ForecastBadge forecastKey={action.forecastKey} />
        </span>
      </dd>
      <dt>유형</dt>
      <dd>
        <InlineEdit
          label="유형"
          kind="custom"
          canEdit={canEdit}
          display={action.type}
          initial={action.type}
          control={(ctx) => <ActionTypeInput value={ctx.value} onChange={ctx.onChange} onSelectOption={(o) => ctx.commit(o.value)} />}
          onSave={(value) => onSave(typePatch(value, types))}
        />
      </dd>
      <dt>진행사항</dt>
      <dd className="dd-pre">
        <InlineEdit
          label="진행사항"
          fill
          saveButtons
          otherSaving={saving}
          kind="custom"
          canEdit={canEdit}
          display={text(action.progress)}
          initial={action.progress ?? ''}
          control={ActionTextArea}
          onSave={(value) => onSave(progressPatch(action, value))}
        />
      </dd>
      <dt>Next Action</dt>
      <dd className="dd-pre">
        <InlineEdit
          label="Next Action · Due Date"
          fill
          saveButtons
          otherSaving={saving}
          kind="custom"
          canEdit={canEdit}
          display={text(action.nextAction)}
          initial={encodePair(action.nextAction ?? '', action.dueDate ?? '')}
          control={ActionNextPairInput}
          onSave={(value) => onSave(nextActionPatch(action, value))}
        />
      </dd>
      <dt>Due Date</dt>
      <dd>{text(action.dueDate)}</dd>
      <dt>Next Action 상태</dt>
      <dd>
        {action.nextActionStatus === null ? (
          '—'
        ) : (
          <NextActionStatusCell action={action} canChange={canEdit} busy={statusBusy} showClosedOn onChange={onChangeStatus} />
        )}
      </dd>
    </dl>
  )
}
