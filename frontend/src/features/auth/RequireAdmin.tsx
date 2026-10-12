import { Navigate, Outlet } from 'react-router'
import { usePermissions } from './hooks'

/** 관리자 전용 화면의 가드. RequireAuth 안에서 쓰므로 사용자(me)는 이미 확정되어 있다. */
export function RequireAdmin() {
  const { isAdmin } = usePermissions()
  if (!isAdmin) return <Navigate to="/deals" replace />
  return <Outlet />
}
