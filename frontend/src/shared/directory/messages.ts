import { ApiError, errorMessage } from '../api/problem'

const STAGE_MESSAGES: Record<string, string> = {
  connect: 'AD 서버에 연결하지 못했습니다. 호스트·포트·방화벽을 확인하세요.',
  tls: 'SSL/StartTLS 연결을 맺지 못했습니다. 보안 연결 방식과 포트가 서버 설정과 맞는지 확인하세요.',
  service_bind: '바인드 계정으로 AD에 로그인하지 못했습니다. 바인드 계정과 바인드 비밀번호를 확인하세요.',
  base_dn: 'AD에서 Base DN(defaultNamingContext)을 찾지 못했습니다. AD 서버 설정과 바인드 계정의 조회 권한을 확인하세요.',
  search: '사용자 검색에 실패했습니다. 사용자 필터와 바인드 계정의 검색 권한을 확인하세요.',
  bind: '입력한 관리자 비밀번호로 AD에 로그인하지 못했습니다. 관리자 비밀번호를 확인하세요.',
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
