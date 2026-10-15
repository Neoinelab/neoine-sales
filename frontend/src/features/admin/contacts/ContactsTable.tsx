import type { ContactRow } from '../../../shared/model/types'

interface Props {
  rows: readonly ContactRow[]
  /** 검색어나 구분 조건이 있는지(빈 목록 문구를 가른다). */
  filtered: boolean
  onEdit: (row: ContactRow) => void
  onDelete: (row: ContactRow) => void
}

/** 연락처 표. 연결 Deal이 있어도 삭제 버튼은 열어 두고, 클릭 후 서버 거부 문구를 보여준다(409 흉내). */
export function ContactsTable({ rows, filtered, onEdit, onDelete }: Props) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>구분</th>
            <th>회사명</th>
            <th>담당자명</th>
            <th>직급</th>
            <th>이메일</th>
            <th>전화</th>
            <th>연결 Deal</th>
            <th>작업</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td>
                <span className="badge">{c.kind === 'customer' ? '고객' : '파트너'}</span>
              </td>
              <td>{c.company}</td>
              <td>{c.name}</td>
              <td>{c.title === '' ? '-' : c.title}</td>
              <td>{c.email ?? '-'}</td>
              <td>{c.phone ?? '-'}</td>
              <td className="num stat">{c.dealCount}</td>
              <td>
                <div className="row-actions">
                  <button type="button" className="small" onClick={() => onEdit(c)}>
                    수정
                  </button>
                  <button type="button" className="small" onClick={() => onDelete(c)}>
                    삭제
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={8} className="empty">
                {filtered ? '조건에 맞는 연락처가 없습니다.' : '등록된 연락처가 없습니다.'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
