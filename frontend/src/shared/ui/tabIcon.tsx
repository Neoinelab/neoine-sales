/** 탭 글자 왼쪽에 붙이는 장식 아이콘(20px 선 그림). 색은 글자색(currentColor)을 따라 선택·비선택 색이 함께 바뀐다. */
export function tabIcon(path: string) {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
