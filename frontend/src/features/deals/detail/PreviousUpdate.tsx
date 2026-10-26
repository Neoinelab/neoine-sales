import type { DealAction } from '../../../shared/model/types'
import { CheckboxField } from '../../../shared/ui/fields'

interface Props {
  previous: DealAction
  /** 채우기 버튼을 눌렀는지. 눌러야 종료 체크박스(또는 안내)가 나온다. */
  filled: boolean
  /** 이 Next Action을 종료(수행)로 바꿀 수 있는지(Open이고 admin 또는 본인 Action). */
  closable: boolean
  /** 이미 종료된 Next Action이면 체크박스도 안내도 없다. */
  open: boolean
  closeChecked: boolean
  onFill: (text: string) => void
  onCloseChange: (checked: boolean) => void
}

/**
 * 이전 Update 참조 카드: Next Action이 있는 가장 최근 Action을 읽기 전용으로 보여 주고 Next Action을 진행사항으로 채울 수 있다.
 * 채운 뒤에는 저장 때 이전 Next Action을 종료(수행)로 바꿀지(기본 켜짐) 고른다.
 */
export function PreviousUpdate({ previous, filled, closable, open, closeChecked, onFill, onCloseChange }: Props) {
  const next = previous.nextAction
  return (
    <aside aria-label="이전 Update" className="dd-prev">
      <h3>이전 Update</h3>
      <dl className="dd-dl">
        <dt>진행사항</dt>
        <dd>{previous.progress ?? '—'}</dd>
        <dt>Next Action</dt>
        <dd>{next ?? '—'}</dd>
        <dt>Due</dt>
        <dd>{previous.dueDate ?? '—'}</dd>
      </dl>
      {next !== null && (
        <button type="button" className="dd-small" onClick={() => onFill(next)}>
          이전 Next Action을 진행사항에 채우기
        </button>
      )}
      {filled && open && closable && (
        <CheckboxField label="저장 시 이전 Next Action을 종료(수행)로 바꿈" name="closePrevious" checked={closeChecked} onChange={onCloseChange} />
      )}
      {filled && open && !closable && <p className="hint">다른 담당자의 Next Action이라 상태는 바꾸지 않습니다.</p>}
    </aside>
  )
}
