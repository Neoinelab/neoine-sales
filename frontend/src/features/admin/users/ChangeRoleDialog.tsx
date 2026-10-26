import { useState } from 'react'
import type { Role, User } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { SelectField } from '../../../shared/ui/fields'

const ROLES: readonly Role[] = ['admin', 'sales', 'user']

interface Props {
  user: User
  busy: boolean
  onConfirm: (role: Role) => void
  onCancel: () => void
}

/** 역할 변경 대화상자. 현재와 같은 역할이면 변경할 수 없다. sales가 아니게 되면 Owner 지정 불가 안내를 보인다. */
export function ChangeRoleDialog({ user, busy, onConfirm, onCancel }: Props) {
  const [role, setRole] = useState<Role>(user.role)
  return (
    <ConfirmDialog
      title="역할 변경"
      confirmLabel="변경"
      busy={busy}
      confirmDisabled={role === user.role}
      message={
        <>
          <p>{`${user.loginId} (${user.name}) 사용자의 역할을 바꿉니다.`}</p>
          <p>바뀐 역할은 그 사용자의 다음 요청부터 적용됩니다(다시 로그인할 필요 없음).</p>
        </>
      }
      onConfirm={() => onConfirm(role)}
      onCancel={onCancel}
    >
      <SelectField label="역할" name="role" value={role} onChange={(v) => setRole(v as Role)}>
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {r}
          </option>
        ))}
      </SelectField>
      {user.role === 'sales' && role !== 'sales' && (
        <p className="hint">sales가 아니면 새 Deal의 Owner로 지정할 수 없습니다. 이미 Owner인 Deal은 그대로 남습니다.</p>
      )}
    </ConfirmDialog>
  )
}
