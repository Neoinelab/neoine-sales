import { errorMessage } from '../api/problem'

/** 오류를 role="alert"로 보여준다. 화면별 문구가 필요하면 format으로 바꾼다. */
export function ErrorBanner({ error, format = errorMessage }: { error: unknown; format?: (error: unknown) => string }) {
  if (!error) return null
  return (
    <p role="alert" className="error">
      {format(error)}
    </p>
  )
}
