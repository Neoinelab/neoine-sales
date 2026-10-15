import { screen } from '@testing-library/react'

/** 이름으로 목록 행을 찾는다(행의 접근 가능한 이름에 Deal 이름이 들어 있다). */
export async function rowOf(name: string | RegExp) {
  return screen.findByRole('row', { name })
}

/** 머리글 행을 뺀 데이터 행. 빠른 보기를 펼치지 않은 상태에서 쓴다. */
export function dataRows() {
  return screen.getAllByRole('row').slice(1)
}

/** 오늘로부터 offset일 뒤의 로컬 날짜(YYYY-MM-DD). */
export function isoDay(offset: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offset)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}
