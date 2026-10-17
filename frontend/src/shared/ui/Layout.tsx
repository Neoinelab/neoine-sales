import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router'
import { useLogout, usePermissions } from '../../data/auth'
import { visibleMenu } from '../model/permissions'
import { useDealListPath } from './useDealListPath'

const MENU_LABELS: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/deals': 'Deals',
  '/forecast': 'Forecast',
  '/reports': 'Reports',
  '/admin': 'Admin',
}

/** 상단 메뉴(사용자 4개 + admin에게만 Admin), 사용자 표시, 로그아웃. */
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
          <strong className="brand-name">NEOINE</strong>
          <span className="brand-sub">영업관리</span>
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
              <span className="user-label">
                {me.name} ({me.role})
              </span>
            )}
            <button
              type="button"
              className="logout"
              onClick={() => logout.mutate(undefined, { onSuccess: () => void navigate('/login') })}
            >
              로그아웃
            </button>
          </div>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </>
  )
}
