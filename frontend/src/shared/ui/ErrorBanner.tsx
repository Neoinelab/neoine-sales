import { errorMessage } from '../api/problem'

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="error">
      {errorMessage(error)}
    </p>
  )
}
