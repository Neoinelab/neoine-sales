import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { AdminLayout } from './features/admin/AdminLayout'
import { ContactsPage } from './features/admin/contacts/ContactsPage'
import { DealManagementPage } from './features/admin/deal-management/DealManagementPage'
import { IntegrationsPage } from './features/admin/integrations/IntegrationsPage'
import { UsersPage } from './features/admin/users/UsersPage'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAdmin } from './features/auth/RequireAdmin'
import { RequireAuth } from './features/auth/RequireAuth'
import { RequireWrite } from './features/auth/RequireWrite'
import { DealFormPage } from './features/deals/form/DealFormPage'
import { DealDetailPage } from './features/deals/detail/DealDetailPage'
import { DealsPage } from './features/deals/list/DealsPage'
import { ForecastPage } from './features/forecast/ForecastPage'
import { ReportsPage } from './features/reports/ReportsPage'
import { SetupPage } from './features/setup/SetupPage'

// Chart.js가 커서 Dashboard는 처음 열 때 내려받는다(나머지 화면의 첫 로딩을 늘리지 않는다).
const DashboardPage = lazy(() => import('./features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))

// 디자이너·편집·보기 화면은 커서 처음 열 때 내려받는다.
const ReportDesignerPage = lazy(() => import('./features/reports/designer/ReportDesignerPage').then((m) => ({ default: m.ReportDesignerPage })))
const ReportEditPage = lazy(() => import('./features/reports/designer/ReportEditPage').then((m) => ({ default: m.ReportEditPage })))
const ReportViewPage = lazy(() => import('./features/reports/view/ReportViewPage').then((m) => ({ default: m.ReportViewPage })))

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<p className="hint">불러오는 중…</p>}>{children}</Suspense>
}

/** 라우트는 이 파일 한 곳에서만 정의한다(계획 5장). */
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      {/* 옛 주소: 사용자 관리·설정은 Admin 새 주소로(고객·파트너·활동 검색 주소는 catch-all이 처리) */}
      <Route path="/users" element={<Navigate to="/admin/users" replace />} />
      <Route path="/settings" element={<Navigate to="/admin/integrations" replace />} />
      <Route element={<RequireAuth />}>
        <Route index element={<Navigate to="/deals" replace />} />
        <Route path="/dashboard" element={
            <Suspense fallback={<p className="hint">불러오는 중…</p>}>
              <DashboardPage />
            </Suspense>
          } />
        <Route path="/deals" element={<DealsPage />} />
        <Route element={<RequireWrite />}>
          <Route path="/deals/new" element={<DealFormPage />} />
          <Route path="/deals/:dealCode/edit" element={<DealFormPage />} />
        </Route>
        <Route path="/deals/:dealCode" element={<DealDetailPage />} />
        <Route path="/forecast" element={<ForecastPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/reports/new" element={<Lazy><ReportDesignerPage /></Lazy>} />
        <Route path="/reports/:id" element={<Lazy><ReportViewPage /></Lazy>} />
        <Route path="/reports/:id/edit" element={<Lazy><ReportEditPage /></Lazy>} />
        <Route element={<RequireAdmin />}>
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<Navigate to="/admin/users" replace />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="deal" element={<DealManagementPage />} />
            <Route path="contacts" element={<ContactsPage />} />
            <Route path="integrations" element={<IntegrationsPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
