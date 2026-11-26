import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { useLogout, usePermissions } from '../../data/auth'
import { visibleMenu } from '../model/permissions'
import { useDealListPath } from './useDealListPath'
import { UserMenu } from './UserMenu'

const MENU_LABELS: Record<string, string> = {
  '/contracts': '계약관리',
  '/dashboard': 'Dashboard',
  '/deals': 'Deals',
  '/partner-activities': '파트너 Activity',
  '/forecast': 'Forecast',
  '/reports': 'Reports',
  '/admin': 'Admin',
}

/** 상단 메뉴(사용자 6개 + admin에게만 Admin)와 사용자 아이콘 메뉴(이름·내 정보·로그아웃). */
export function Layout() {
  const { me, role } = usePermissions()
  const logout = useLogout()
  const navigate = useNavigate()
  const menu = visibleMenu(role)
  const dealsPath = useDealListPath()
  const [open, setOpen] = useState(false)
  return (
    <>
      <header className="topbar">
        <span className="brand">
          <a href="/" className="logo-link">
            <img src="logo.png" alt="사이트 로고" className="logo-img"/>
          </a>
        </span>
        <button
            type="button"
            className="topbar-toggle"
            aria-label="메뉴 열기"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
            <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
        </button>
        <div className={open ? 'topbar-menu open' : 'topbar-menu'}>
          <nav aria-label="주 메뉴">
            {menu.map((to) => (
              <NavLink key={to} to={to === '/deals' ? dealsPath : to} onClick={() => setOpen(false)}>
                {MENU_LABELS[to] ?? to}
              </NavLink>
            ))}
          </nav>
          <span className="spacer" />
          <div className="topbar-user">
            {me && (
              <UserMenu
                me={me}
                onPicked={() => setOpen(false)}
                onLogout={() => logout.mutate(undefined, { onSuccess: () => void navigate('/login') })}
              />
            )}
          </div>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </>
  )
}
