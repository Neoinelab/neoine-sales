import { ApiError, errorMessage } from '../api/problem'

const STAGE_MESSAGES: Record<string, string> = {
  connect: 'AD 서버에 연결할 수 없습니다. 서버 URL과 네트워크를 확인하세요.',
  tls: 'TLS 연결을 확인하지 못했습니다. CA 인증서와 StartTLS 설정을 확인하세요.',
  bind: '바인드 템플릿 또는 계정 정보를 확인하세요.',
  search: '사용자 검색에 실패했습니다. Base DN과 사용자 검색 필터를 확인하세요.',
}

/** AD 검증이 실패한 단계에 맞는 안내. 모르는 단계면 undefined. */
export function stageMessage(stage: string | null | undefined): string | undefined {
  return stage ? STAGE_MESSAGES[stage] : undefined
}

/** AD 설정 요청의 실패를 사용자 문구로 바꾼다(영문 type 코드는 보이지 않는다). */
export function directoryErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === 'directory-verification-failed') return stageMessage(error.stage) ?? errorMessage(error)
    if (error.status === 429) return '시도가 너무 많습니다. 잠시 후 다시 시도하세요.'
  }
  return errorMessage(error)
}
