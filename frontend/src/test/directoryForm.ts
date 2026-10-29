import { fireEvent, screen } from '@testing-library/react'
import type { UserEvent } from '@testing-library/user-event'

/** 입력 칸의 값을 통째로 바꾼다(`{`·`}`가 들어간 값도 그대로 넣으려고 userEvent.type을 쓰지 않는다). */
export function setField(label: RegExp | string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

/** 보안 연결 선택 칸에서 방식을 고른다(`none`·`ssl`·`starttls`). */
export async function selectSecurity(user: UserEvent, mode: 'none' | 'ssl' | 'starttls') {
  await user.selectOptions(screen.getByLabelText(/보안 연결/), mode)
}

/**
 * AD 서버 설정 폼(마법사 1단계·설정 화면 공통)의 필수 칸을 채운다.
 * 칸은 호스트·포트·보안 연결·바인드 계정·바인드 비밀번호·사용자 검색 필터·연결 제한 시간(초) 7개뿐이다.
 */
export function fillDirectoryForm(
  over: Partial<Record<'host' | 'bindAccount' | 'bindPassword', string>> = {},
) {
  setField(/^호스트/, over.host ?? 'dc1.corp.test')
  setField(/^바인드 계정/, over.bindAccount ?? 'CORP\\svc-sales')
  setField(/^바인드 비밀번호/, over.bindPassword ?? 'Svc-Dummy-pw-1!')
}
