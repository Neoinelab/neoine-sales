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
import { ComingSoonPage } from './features/placeholder/ComingSoonPage'
import { SetupPage } from './features/setup/SetupPage'
import { MockBanner } from './shared/ui/MockBanner'

/** 라우트는 이 파일 한 곳에서만 정의한다(계획 5장). 목업 배지는 모든 화면 위에 한 번만 그린다. */
export function App() {
  return (
    <>
      <MockBanner />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/setup" element={<SetupPage />} />
        {/* 옛 주소: 사용자 관리·설정은 Admin 새 주소로, 고객·파트너·활동 검색은 폐지 */}
        <Route path="/users" element={<Navigate to="/admin/users" replace />} />
        <Route path="/settings" element={<Navigate to="/admin/integrations" replace />} />
        <Route path="/customers" element={<Navigate to="/deals" replace />} />
        <Route path="/partners" element={<Navigate to="/deals" replace />} />
        <Route path="/actions" element={<Navigate to="/deals" replace />} />
        <Route element={<RequireAuth />}>
          <Route index element={<Navigate to="/deals" replace />} />
          <Route path="/dashboard" element={<ComingSoonPage title="Dashboard" />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route element={<RequireWrite />}>
            <Route path="/deals/new" element={<DealFormPage />} />
            <Route path="/deals/:dealCode/edit" element={<DealFormPage />} />
          </Route>
          <Route path="/deals/:dealCode" element={<DealDetailPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
          <Route path="/reports" element={<ComingSoonPage title="Reports" />} />
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
    </>
  )
}
