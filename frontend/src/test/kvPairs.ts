/** 라벨-값 격자 테스트 도우미(운영 코드에서 쓰지 않는다). 타일 안 첫 dl의 dt/dd를 [라벨, 값] 쌍으로 읽는다. */
export function kvPairs(root: HTMLElement): Array<[string, string]> {
  const dl = root.querySelector('dl')
  if (!dl) throw new Error('dl이 없습니다.')
  return Array.from(dl.querySelectorAll('dt')).map((dt): [string, string] => [
    dt.textContent ?? '',
    dt.nextElementSibling?.textContent ?? '',
  ])
}

/** 라벨 이름으로 dd 요소를 찾는다. */
export function kvValue(root: HTMLElement, label: string): HTMLElement {
  const dl = root.querySelector('dl')
  const dt = dl ? Array.from(dl.querySelectorAll('dt')).find((el) => el.textContent === label) : undefined
  const dd = dt?.nextElementSibling
  if (!(dd instanceof HTMLElement)) throw new Error(`${label} 항목이 없습니다.`)
  return dd
}
