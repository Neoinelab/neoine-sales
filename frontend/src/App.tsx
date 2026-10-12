import { Navigate, Route, Routes } from 'react-router'
import { ActionsSearchPage } from './features/actions/ActionsSearchPage'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAdmin } from './features/auth/RequireAdmin'
import { RequireAuth } from './features/auth/RequireAuth'
import { CustomersPage } from './features/customers/CustomersPage'
import { DealDetailPage } from './features/deals/DealDetailPage'
import { DealsPage } from './features/deals/DealsPage'
import { PartnersPage } from './features/partners/PartnersPage'
import { SettingsPage } from './features/settings/SettingsPage'
import { SetupPage } from './features/setup/SetupPage'
import { UsersPage } from './features/users/UsersPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/setup" element={<SetupPage />} />
      <Route element={<RequireAuth />}>
        <Route index element={<Navigate to="/deals" replace />} />
        <Route path="/deals" element={<DealsPage />} />
        <Route path="/deals/:dealId" element={<DealDetailPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/partners" element={<PartnersPage />} />
        <Route path="/actions" element={<ActionsSearchPage />} />
        <Route element={<RequireAdmin />}>
          <Route path="/users" element={<UsersPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
