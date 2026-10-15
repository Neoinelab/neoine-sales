import { useState } from 'react'

/**
 * 새 조건으로 다시 조회하는 동안(data가 잠깐 undefined) 직전 결과를 계속 보여주기 위한 도우미.
 * 표가 사라졌다 다시 생기는 깜빡임(과 포커스·스크롤 초기화)을 막는다. 렌더 중 상태 조정 패턴을 쓴다.
 */
export function useLatest<T>(value: T | undefined): T | undefined {
  const [last, setLast] = useState<T | undefined>(value)
  if (value !== undefined && value !== last) setLast(value)
  return value ?? last
}
