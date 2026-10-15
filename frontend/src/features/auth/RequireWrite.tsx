import { Navigate, Outlet } from 'react-router'
import { usePermissions } from '../../data/auth'

/** 등록·수정 화면의 가드(sales/admin). user는 /deals로 보낸다. */
export function RequireWrite() {
  const { canWrite } = usePermissions()
  if (!canWrite) return <Navigate to="/deals" replace />
  return <Outlet />
}
