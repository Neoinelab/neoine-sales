import { fireEvent, screen } from '@testing-library/react'

/** 입력 칸의 값을 통째로 바꾼다(`{`·`}`가 들어간 값도 그대로 넣으려고 userEvent.type을 쓰지 않는다). */
export function setField(label: RegExp | string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } })
}

/** AD 서버 설정 폼(마법사 1단계·설정 화면 공통)의 필수 칸을 채운다. */
export function fillDirectoryForm(over: Partial<Record<'urls' | 'bind' | 'baseDn', string>> = {}) {
  setField(/서버 URL/, over.urls ?? 'ldaps://dc1.corp.test\nldaps://dc2.corp.test:6636')
  setField(/바인드 템플릿/, over.bind ?? 'CORP\\{login_id}')
  setField(/Base DN/, over.baseDn ?? 'dc=corp,dc=test')
}
