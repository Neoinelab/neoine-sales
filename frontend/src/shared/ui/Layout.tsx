import { NavLink, Outlet } from 'react-router'
import { useLogout, useMe, usePermissions } from '../../features/auth/hooks'

const links = [
  { to: '/deals', label: '딜' },
  { to: '/customers', label: '고객' },
  { to: '/partners', label: '파트너' },
  { to: '/actions', label: '활동 검색' },
]

const adminLinks = [
  { to: '/users', label: '사용자 관리' },
  { to: '/settings', label: '설정' },
]

export function Layout() {
  const me = useMe()
  const logout = useLogout()
  const { isAdmin } = usePermissions()
  const menu = isAdmin ? [...links, ...adminLinks] : links
  return (
    <>
      <header className="topbar">
        <strong>neoine-sales</strong>
        <nav aria-label="주 메뉴">
          {menu.map((link) => (
            <NavLink key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <span className="spacer" />
        {me.data && (
          <span>
            {me.data.name} ({me.data.role})
          </span>
        )}
        <button type="button" onClick={() => logout.mutate()}>
          로그아웃
        </button>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </>
  )
}
