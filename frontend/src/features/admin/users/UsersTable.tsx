import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { User, UserListFilter } from '../../../shared/model/types'

function emptyMessage(filter: UserListFilter): string {
  return filter === 'resigned' ? '퇴사한 사용자가 없습니다.' : '등록된 사용자가 없습니다.'
}

interface Props {
  users: readonly User[]
  filter: UserListFilter
  /** 로그인한 사용자 id. 본인 행에는 역할 변경·삭제 버튼을 두지 않는다(마지막 admin 보호). */
  meId: number | undefined
  onChangeRole: (user: User) => void
  onDelete: (user: User) => void
}

/** 사용자 목록 표. 퇴사자는 이름 뒤에 (퇴사)를 붙이고 삭제 버튼이 없다. */
export function UsersTable({ users, filter, meId, onChangeRole, onDelete }: Props) {
  return (
    <div className="table-wrap">
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
            <th>
              <span className="sr-only">작업</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>{u.loginId}</td>
              <td>{u.role}</td>
              <td>{userLabel(u)}</td>
              <td>{formatDateTime(u.createdAt)}</td>
              <td>{u.createdBy ? userLabel(u.createdBy) : '-'}</td>
              <td>{u.lastLoginAt ? formatDateTime(u.lastLoginAt) : '-'}</td>
              <td>{u.resignedAt ? formatDateTime(u.resignedAt) : '-'}</td>
              <td>{u.resignReason ?? '-'}</td>
              <td>
                {u.status === 'active' && u.id !== meId && (
                  <>
                    <button type="button" className="small" onClick={() => onChangeRole(u)}>
                      역할 변경
                    </button>{' '}
                    <button type="button" className="small" onClick={() => onDelete(u)}>
                      삭제
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
          {users.length === 0 && (
            <tr>
              <td colSpan={9} className="empty">
                {emptyMessage(filter)}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
