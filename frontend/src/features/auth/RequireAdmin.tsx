import { Navigate, Outlet } from 'react-router'
import { usePermissions } from '../../data/auth'

/** 관리자 전용 화면의 가드. RequireAuth 안에서 쓰므로 사용자(me)는 이미 확정되어 있다. 아니면 /deals로 보낸다. */
export function RequireAdmin() {
  const { isAdmin } = usePermissions()
  if (!isAdmin) return <Navigate to="/deals" replace />
  return <Outlet />
}
