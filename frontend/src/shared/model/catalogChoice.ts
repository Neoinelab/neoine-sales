/** 카탈로그(Action 유형·BANT Label) 선택: 있는 항목의 id 또는 서버가 찾거나 만들 이름 중 하나. */
export type CatalogChoice = { id: string } | { name: string }

/**
 * 입력 텍스트를 선택으로 바꾼다. trim이 비면 null(선택 안 함),
 * 대소문자 무시로 같은 항목이 있으면 `{id}`, 아니면 trim한 `{name}`(부분 일치는 새 이름이다).
 */
export function toChoice(text: string, options: readonly { id: string; name: string }[]): CatalogChoice | null {
  const name = text.trim()
  if (name === '') return null
  const lower = name.toLowerCase()
  const found = options.find((option) => option.name.toLowerCase() === lower)
  return found ? { id: found.id } : { name }
}
