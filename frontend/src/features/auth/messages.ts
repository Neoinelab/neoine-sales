import { ApiError, errorMessage } from '../../shared/api/problem'

/** 로그인·최초 관리자 등록 실패 문구. 401은 서버 detail을 그대로 쓴다. */
export function authErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.'
    if (error.status === 503) return 'AD 서버에 연결할 수 없습니다. 잠시 후 다시 시도하세요.'
  }
  return errorMessage(error)
}
