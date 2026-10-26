import { useState } from 'react'
import { useChangeUserRole, useRemoveUser, useUsers } from '../../../data/users'
import { usePermissions } from '../../../data/auth'
import type { Role, User, UserListFilter } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SelectField } from '../../../shared/ui/fields'
import { Notice } from '../../../shared/ui/Notice'
import '../admin.css'
import { AddUserForm } from './AddUserForm'
import { ChangeRoleDialog } from './ChangeRoleDialog'
import { UsersTable } from './UsersTable'

const OUTCOME_TEXT = { deleted: '삭제', resigned: '퇴사 처리' } as const

/** 관리자 전용: 로그인할 수 있는 AD 계정과 역할을 관리한다. 삭제는 연결된 데이터가 있으면 퇴사 처리된다. */
export function UsersPage() {
  const [filter, setFilter] = useState<UserListFilter>('active')
  const [target, setTarget] = useState<User | null>(null)
  const [roleTarget, setRoleTarget] = useState<User | null>(null)
  const [result, setResult] = useState<string | null>(null)
  const users = useUsers(filter)
  const { me } = usePermissions()
  const remove = useRemoveUser()
  const changeRole = useChangeUserRole()

  function confirmDelete(user: User) {
    setResult(null)
    changeRole.reset()
    remove.reset()
    remove.mutate(user.id, {
      onSuccess: (r) => setResult(`${user.loginId} 사용자가 ${OUTCOME_TEXT[r.outcome]}되었습니다.`),
      onSettled: () => setTarget(null),
    })
  }

  function confirmRole(user: User, role: Role) {
    setResult(null)
    remove.reset()
    changeRole.reset()
    changeRole.mutate(
      { id: user.id, role },
      {
        onSuccess: () => setResult(`${user.loginId} 사용자의 역할이 ${user.role}에서 ${role}(으)로 바뀌었습니다.`),
        onSettled: () => setRoleTarget(null),
      },
    )
  }

  function startRoleChange(user: User) {
    changeRole.reset()
    setRoleTarget(user)
  }

  return (
    <section className="admin-page" aria-labelledby="users-title">
      <h2 id="users-title">사용자 관리</h2>
      <ErrorBanner error={users.error ?? remove.error ?? changeRole.error} />
      {result && (
        <Notice kind="success" onClose={() => setResult(null)}>
          {result}
        </Notice>
      )}
      <AddUserForm />
      <div className="admin-form-row">
        <SelectField label="상태" name="status" value={filter} onChange={(v) => setFilter(v as UserListFilter)}>
          <option value="active">재직</option>
          <option value="resigned">퇴사</option>
          <option value="all">전체</option>
        </SelectField>
      </div>
      {users.isPending && <p className="hint">불러오는 중…</p>}
      {users.isSuccess && <UsersTable users={users.data} filter={filter} meId={me?.id} onChangeRole={startRoleChange} onDelete={setTarget} />}
      {roleTarget && (
        <ChangeRoleDialog user={roleTarget} busy={changeRole.isPending} onConfirm={(role) => confirmRole(roleTarget, role)} onCancel={() => setRoleTarget(null)} />
      )}
      {target && (
        <ConfirmDialog
          title="사용자 삭제"
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          message={
            <>
              <p>{`${target.loginId} (${target.name}) 사용자를 삭제할까요?`}</p>
              <p>연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다.</p>
              <p>로그인 세션은 모두 종료됩니다.</p>
            </>
          }
          onConfirm={() => confirmDelete(target)}
          onCancel={() => setTarget(null)}
        />
      )}
    </section>
  )
}
