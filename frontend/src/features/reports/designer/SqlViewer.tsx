/** 서버가 만든 SQL을 읽기 전용으로 보인다(편집 입력 없음). 조회 전에는 안내만 보인다. */
export function SqlViewer({ sql }: { sql: string | null }) {
  if (sql === null) return <p className="hint">조회하면 서버가 만든 SQL이 여기에 보입니다</p>
  return (
    <details className="report-sql">
      <summary>생성 SQL 보기(읽기 전용)</summary>
      {/* 긴 SQL을 키보드로 스크롤할 수 있어야 하므로 읽기 전용 영역에 포커스를 허용한다. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex */}
      <pre tabIndex={0}>{sql}</pre>
    </details>
  )
}
