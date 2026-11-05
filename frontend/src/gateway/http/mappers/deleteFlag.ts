/**
 * Deal 변경 요청 세 가지(수정·단일 변경·Action 등록)의 `delete_license_contracts`.
 * 서버는 생략을 false(유지)로 받지만, 생성 타입은 서버 기본값이 있는 이 필드를 요청에서도 필수로 만든다.
 * 요청하지 않았으면 보내지 않도록(예전 요청 모양 그대로) 선택 필드로 만들고, 호출 지점에서만 생성 타입으로 되돌린다.
 */
export type WithOptionalDeleteFlag<T> = Omit<T, 'delete_license_contracts'> & { delete_license_contracts?: boolean }

export function asRequestBody<T extends { delete_license_contracts: boolean }>(body: WithOptionalDeleteFlag<T>): T {
  return body as T
}
