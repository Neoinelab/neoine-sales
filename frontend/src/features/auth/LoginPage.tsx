import { Navigate } from 'react-router'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { CredentialsForm } from './CredentialsForm'
import { DevLoginForm } from './DevLoginForm'
import { useAuthConfig, useLogin, useMe } from './hooks'
import { authErrorMessage } from './messages'

export function LoginPage() {
  const me = useMe()
  const config = useAuthConfig()
  const login = useLogin()

  if (me.data) return <Navigate to="/" replace />
  const settings = config.data
  if (settings && (settings.needs_directory_setup || settings.needs_admin_setup || !settings.directory_login)) {
    return <Navigate to="/setup" replace />
  }

  return (
    <main className="login">
      <h1>neoine-sales</h1>
      <ErrorBanner error={config.error} />
      <ErrorBanner error={login.error} format={authErrorMessage} />
      {settings?.directory_login && (
        <CredentialsForm submitLabel="로그인" pending={login.isPending} onSubmit={login.mutateAsync} />
      )}
      {settings?.dev_login && <DevLoginForm />}
    </main>
  )
}
