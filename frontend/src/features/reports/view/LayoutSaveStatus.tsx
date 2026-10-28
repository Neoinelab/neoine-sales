import { Link } from 'react-router'
import type { LayoutAutosave } from './useLayoutAutosave'

const READ_ONLY_NOTE = '보기 방식과 배치는 이 화면에서만 바뀌고 저장되지 않습니다'

/** 보기 선택 줄 옆의 저장 상태 줄(`role=status`). 수정 권한이 없으면 저장되지 않는다는 고정 안내만 보인다. */
export function LayoutSaveStatus({ autosave, canEdit }: { autosave: LayoutAutosave; canEdit: boolean }) {
  if (!canEdit) return <span className="hint">{READ_ONLY_NOTE}</span>
  return (
    <p role="status" aria-live="polite" className="hint report-layout-status">
      {autosave.status === 'saving' && '배치 저장 중…'}
      {autosave.status === 'saved' && '배치를 저장했습니다'}
    </p>
  )
}

/** 저장 실패 안내(`role=alert`). 충돌·권한·찾을 수 없음은 멈춘 상태, 그 밖의 실패는 '다시 시도'를 준다. */
export function LayoutSaveAlert({ autosave }: { autosave: LayoutAutosave }) {
  switch (autosave.status) {
    case 'conflict':
      return (
        <p role="alert" className="error">
          다른 사람이 이 리포트를 먼저 수정해 최신 내용을 다시 불러왔습니다. 내가 바꾼 배치는 저장되지 않았습니다. 필요하면 배치를 다시 바꾸세요.
        </p>
      )
    case 'forbidden':
      return (
        <p role="alert" className="error">
          이 리포트를 수정할 권한이 없어 배치를 저장하지 못했습니다. 바꾼 배치는 이 화면에서만 유지됩니다.
        </p>
      )
    case 'notFound':
      return (
        <p role="alert" className="error">
          리포트를 찾을 수 없어 배치를 저장하지 못했습니다. 목록에서 다시 확인하세요. <Link to="/reports">리포트 목록</Link>
        </p>
      )
    case 'failed':
      return (
        <p role="alert" className="error">
          배치를 저장하지 못했습니다. 잠시 뒤 다시 시도하세요.{' '}
          <button type="button" onClick={autosave.retry}>
            다시 시도
          </button>
        </p>
      )
    default:
      return null
  }
}
