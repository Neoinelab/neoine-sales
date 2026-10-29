import { Link } from 'react-router'
import { userLabel } from '../../shared/model/period'
import type { PartnerMeeting, PartnerMeetingSort, SortOrder } from '../../shared/model/types'
import { SortableHeader } from '../../shared/ui/SortableHeader'

const COLUMNS: readonly { label: string; sort: PartnerMeetingSort }[] = [
  { label: '파트너', sort: 'partner' },
  { label: 'Deal', sort: 'deal' },
  { label: '미팅 날짜', sort: 'meetingDate' },
  { label: '미팅 내용', sort: 'content' },
  { label: '작성자', sort: 'author' },
]

interface MeetingTableProps {
  rows: readonly PartnerMeeting[]
  sort: PartnerMeetingSort
  order: SortOrder
  onSort: (column: PartnerMeetingSort) => void
  /** 관리 열을 둘지(쓸 수 있는 역할). */
  manage: boolean
  canEdit: (meeting: PartnerMeeting) => boolean
  onEdit: (meeting: PartnerMeeting) => void
  onDelete: (meeting: PartnerMeeting) => void
}

export function MeetingTable({ rows, sort, order, onSort, manage, canEdit, onEdit, onDelete }: MeetingTableProps) {
  return (
    <div className="table-scroll">
      <table className="meeting-table" aria-label="파트너 미팅 기록">
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <SortableHeader key={column.sort} label={column.label} active={sort === column.sort} order={order} onSort={() => onSort(column.sort)} />
            ))}
            {manage && <SortableHeader label="관리" active={false} order={order} />}
          </tr>
        </thead>
        <tbody>
          {rows.map((meeting) => (
            <tr key={meeting.id}>
              <td>{meeting.partnerCompany}</td>
              <td>
                <Link to={`/deals/${meeting.deal.code}`}>{meeting.deal.name}</Link>
              </td>
              <td className="meeting-date">{meeting.meetingDate}</td>
              <td className="meeting-content">{meeting.content}</td>
              <td>{userLabel(meeting.author)}</td>
              {manage && (
                <td className="meeting-actions">
                  {canEdit(meeting) && (
                    <>
                      <button type="button" onClick={() => onEdit(meeting)}>
                        수정
                      </button>
                      <button type="button" onClick={() => onDelete(meeting)}>
                        삭제
                      </button>
                    </>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
