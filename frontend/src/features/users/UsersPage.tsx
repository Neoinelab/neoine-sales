import { formatDateTime } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { useMe } from '../auth/hooks'
import { AddUserForm } from './AddUserForm'
import { useDeleteUser, useUsers } from './hooks'

/** 관리자 전용: 로그인할 수 있는 AD 계정과 역할을 관리한다. */
export function UsersPage() {
  const users = useUsers()
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
      <AddUserForm />
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
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id}>
                <td>{u.login_id}</td>
                <td>{u.role}</td>
                <td>{u.display_name}</td>
                <td>{formatDateTime(u.created_at)}</td>
                <td>{u.created_by}</td>
                <td>{u.last_login_at ? formatDateTime(u.last_login_at) : '-'}</td>
                <td className="row-actions">
                  {me.data?.subject !== u.login_id && (
                    <button
                      type="button"
                      onClick={() => {
                        if (window.confirm(`${u.login_id} 사용자를 삭제할까요?\n삭제하면 복구할 수 없고 로그인 세션이 모두 종료됩니다.`)) remove.mutate(u.id)
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
                <td colSpan={7}>등록된 사용자가 없습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </section>
  )
}
