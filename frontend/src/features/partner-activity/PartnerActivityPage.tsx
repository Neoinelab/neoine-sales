import { useState } from 'react'
import { usePermissions } from '../../data/auth'
import { usePartnerMeetings } from '../../data/partnerMeetings'
import { canEditMeeting } from '../../shared/model/permissions'
import type { PartnerMeeting } from '../../shared/model/types'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Notice } from '../../shared/ui/Notice'
import { useInfiniteScroll } from '../../shared/ui/useInfiniteScroll'
import { MeetingDeleteDialog } from './MeetingDeleteDialog'
import { MeetingEditDialog } from './MeetingEditDialog'
import { MeetingEntryDialog } from './MeetingEntryDialog'
import { MeetingFilterBar } from './MeetingFilterBar'
import { MeetingTable } from './MeetingTable'
import { useMeetingSearchParams } from './useMeetingSearchParams'
import './partner-activity.css'

/** 파트너 Activity(`/partner-activities`): 파트너 미팅 기록 목록(조건 검색·정렬·무한 스크롤)과 입력·수정·삭제. */
export function PartnerActivityPage() {
  const { role, me, canWrite } = usePermissions()
  const { conditions, query, sort, order, search, reset, toggleSort } = useMeetingSearchParams()
  const meetings = usePartnerMeetings(query)
  const [entering, setEntering] = useState(false)
  const [editing, setEditing] = useState<PartnerMeeting | null>(null)
  const [deleting, setDeleting] = useState<PartnerMeeting | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const { fetchNextPage } = meetings
  const sentinelRef = useInfiniteScroll({
    hasNextPage: meetings.hasNextPage,
    isFetchingNextPage: meetings.isFetchingNextPage,
    fetchNextPage: () => void fetchNextPage(),
    pages: meetings.pageCount,
  })
  const viewer = me && role ? { id: me.id, role } : null
  const loaded = meetings.data !== undefined && !meetings.isPlaceholderData

  return (
    <div className="partner-activity-page">
      <div className="heading">
        <h1>파트너 Activity</h1>
        {canWrite && (
          <button type="button" className="primary" onClick={() => setEntering(true)}>
            미팅 내용 입력
          </button>
        )}
      </div>

      <MeetingFilterBar applied={conditions} onSearch={search} onReset={reset} />

      {notice && (
        <Notice kind="success" onClose={() => setNotice(null)}>
          {notice}
        </Notice>
      )}
      <ErrorBanner error={meetings.error} />

      <MeetingTable
        rows={meetings.items}
        sort={sort}
        order={order}
        onSort={toggleSort}
        manage={canWrite}
        canEdit={(meeting) => viewer !== null && canEditMeeting(viewer, meeting.author.id)}
        onEdit={setEditing}
        onDelete={setDeleting}
      />

      {meetings.isPending && <p className="hint">불러오는 중…</p>}
      {loaded && meetings.total === 0 && <p className="meetings-empty">기록된 미팅이 없습니다.</p>}
      {meetings.hasNextPage && (
        <div ref={sentinelRef} className="meetings-more">
          <button type="button" disabled={meetings.isFetchingNextPage} onClick={() => void fetchNextPage()}>
            더 보기
          </button>
        </div>
      )}
      {loaded && !meetings.hasNextPage && meetings.total > 0 && <p className="hint meetings-end">모두 불러왔습니다 (전체 {meetings.total}건)</p>}

      {entering && (
        <MeetingEntryDialog
          onClose={() => setEntering(false)}
          onSaved={(message) => {
            setEntering(false)
            setNotice(message)
          }}
        />
      )}
      {editing && <MeetingEditDialog meeting={editing} onClose={() => setEditing(null)} />}
      {deleting && <MeetingDeleteDialog meeting={deleting} onClose={() => setDeleting(null)} />}
    </div>
  )
}
