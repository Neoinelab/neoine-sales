import { useState } from 'react'
import { formatDateTime } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { useMe } from '../auth/hooks'
import { AddUserForm } from './AddUserForm'
import { useDeleteUser, useUsers, type AppUser, type UserStatusFilter } from './hooks'

const DELETE_CONFIRM =
  '연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다.\n로그인 세션은 모두 종료됩니다.'
const OUTCOME_MESSAGE = { deleted: '삭제되었습니다', resigned: '퇴사 처리되었습니다' } as const
const REASON_LABEL: Record<string, string> = { resigned: '퇴사' }

/** 퇴사자는 이름 뒤에 (퇴사)를 붙여 구분한다. */
function displayName(u: AppUser): string {
  if (u.status !== 'resigned') return u.display_name ?? ''
  return `${u.display_name ?? u.login_id}(퇴사)`
}

/** 관리자 전용: 로그인할 수 있는 AD 계정과 역할을 관리한다. 삭제는 연결된 데이터가 있으면 퇴사 처리된다. */
export function UsersPage() {
  const [status, setStatus] = useState<UserStatusFilter>('active')
  const users = useUsers(status)
  const me = useMe()
  const remove = useDeleteUser()
  const items = users.data?.items ?? []
  const ready = users.isSuccess && !me.isPending

  return (
    <section>
      <div className="heading">
        <h1>사용자 관리</h1>
      </div>
      <ErrorBanner error={users.error ?? remove.error} />
      {remove.data && <p role="status">{OUTCOME_MESSAGE[remove.data.outcome]}</p>}
      <AddUserForm />
      <SelectField label="상태" name="status" value={status} onChange={(v) => setStatus(v as UserStatusFilter)}>
        <option value="active">재직</option>
        <option value="resigned">퇴사</option>
        <option value="all">전체</option>
      </SelectField>
      {users.isPending && <p>불러오는 중…</p>}
      {ready && (
        <table>
          <thead>
            <tr>
              <th>아이디</th>
              <th>역할</th>
              <th>이름</th>
              <th>등록일</th>
              <th>등록자</th>
              <th>마지막 로그인</th>
              <th>퇴사 일시</th>
              <th>퇴사 사유</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id}>
                <td>{u.login_id}</td>
                <td>{u.role}</td>
                <td>{displayName(u)}</td>
                <td>{formatDateTime(u.created_at)}</td>
                <td>{u.created_by.label}</td>
                <td>{u.last_login_at ? formatDateTime(u.last_login_at) : '-'}</td>
                <td>{u.deleted_at ? formatDateTime(u.deleted_at) : '-'}</td>
                <td>{u.delete_reason ? (REASON_LABEL[u.delete_reason] ?? u.delete_reason) : '-'}</td>
                <td className="row-actions">
                  {u.status === 'active' && me.data?.user_id !== u.id && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`${u.login_id} 사용자를 삭제할까요?\n${DELETE_CONFIRM}`)) remove.mutate(u.id)
                      }}
                    >
                      삭제
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={9}>{status === 'resigned' ? '퇴사한 사용자가 없습니다.' : '등록된 사용자가 없습니다.'}</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}
