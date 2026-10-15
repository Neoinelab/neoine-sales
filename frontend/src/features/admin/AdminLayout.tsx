import { NavLink, Outlet } from 'react-router'
import './admin.css'

const SUB_MENU = [
  { to: '/admin/users', label: '사용자 관리' },
  { to: '/admin/deal', label: 'Deal 관리' },
  { to: '/admin/contacts', label: 'contacts 관리' },
  { to: '/admin/integrations', label: '외부연동' },
]

/** Admin 공통 틀(제목 + 좌측 서브 메뉴 + Outlet). 라우트 가드(RequireAdmin)는 App이 건다. 6.7 */
export function AdminLayout() {
  return (
    <div className="admin-layout">
      <h1>Admin &gt; Settings</h1>
      <div className="admin-body">
        <nav aria-label="Admin 메뉴" className="admin-nav">
          {SUB_MENU.map((item) => (
            <NavLink key={item.to} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="admin-content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
