# Meeting single entry implementation evidence

Implemented scope: `frontend/src/features/partner-activity/**`, `frontend/src/test/partnerMeetings.ts`. No backend, API, dependency, CSS, or commit change. Parent owns docs and real-browser visual QA.

## Implementation

- New-entry state holds one `EntryRow`; existing batch transform receives `[row]`, preserving the POST API.
- Removed add/delete controls, their handlers and shared-row props, and content key interception from both entry and edit dialogs.
- Removed the edit Save focus ref. The shared textarea retains `rows={6}` and native Enter/Shift+Enter behavior.
- Preserved explicit Save, partner/date navigation, validation and server-error placement, close/unsaved confirmation, and permissions/list delete actions.
- Removed production-dead `MAX_ROWS`, `firstMissingField`, and `isComplete` plus their obsolete tests. Batch/error transformation helpers retain production consumers.

## Evidence ledger

All invocations below run from `frontend/` using installed local binaries. Initial corepack dispatch failed because its cached pnpm entry file was absent; no dependency install occurred, and local binaries were used.

| Success criterion | Exact scenario | Invocation | Binary observable | Captured artifact |
| --- | --- | --- | --- | --- |
| Regression fails before implementation | Opening entry has no row controls; entry Enter with complete/missing-partner/invalid-date input; edit Enter preserves newline | `./node_modules/.bin/vitest run src/features/partner-activity/MeetingEntryDialog.keys.test.tsx src/features/partner-activity/PartnerActivityPage.entry.test.tsx src/features/partner-activity/MeetingEditDialog.test.tsx` | Exit 1; 5 failed / 28 passed; failures report missing newline and unexpected row-add button | `.omo/evidence/meeting-single-entry/red.log` and `/tmp/neoine-meeting-red.log` |
| Single entry and native newline, no implicit save/focus jump | `opens a dialog with one empty row, focus on the partner, and today as the default date`; `keeps native content newlines without saving or moving focus: $name`; `keeps a native newline in edit content without saving: %s`; IME Enter leaves default unblocked | Unit invocation below | Exit 0; all scenarios pass; persisted count remains 12 before Save | `.omo/evidence/meeting-single-entry/unit.log` |
| Explicit Save persists one multiline meeting and edit multiline text | `saves one meeting, closes the dialog and shows the saved count and list entry`; `shows the saved author as the logged-in user and keeps line breaks`; `saves a new date and content, closes the dialog and shows the record in its new place`; `sends only the three fields of a row to the server` | Unit invocation below | Exit 0; single create item, total increases to 13, entry and edit preserve three lines | `.omo/evidence/meeting-single-entry/unit.log` |
| Navigation, validation, server errors, close and permission/list actions remain | Entire partner-activity unit folder, HTTP partnerMeetings contract tests, fake partnerMeetings tests | Unit invocation below | Exit 0; 14 files / 210 tests passed | `.omo/evidence/meeting-single-entry/unit.log` and `/tmp/neoine-meeting-unit.log` |
| Type safety | Whole frontend `tsc` check | `./node_modules/.bin/tsc --noEmit` | `tsc exit=0` | `.omo/evidence/meeting-single-entry/typecheck.log` and `/tmp/neoine-meeting-typecheck.log` |
| Lint | Partner activity and shared meeting test helper | `./node_modules/.bin/eslint src/features/partner-activity src/test/partnerMeetings.ts` | `eslint exit=0` | `.omo/evidence/meeting-single-entry/eslint.log` and `/tmp/neoine-meeting-eslint.log` |
| Source size audit | 11 changed TypeScript/TSX files | Count nonblank/non-`//` lines with Node filesystem reader | All <=166 lines | `.omo/evidence/meeting-single-entry/line-counts.log` |

Unit invocation: `./node_modules/.bin/vitest run src/features/partner-activity src/gateway/http/partnerMeetings.test.ts src/test/fake/gateway/partnerMeetings.test.ts`.

First intermediate partner-activity-only run passed 158 tests. Initial typecheck found a newly written test query missing `sort`/`order`; fixed it, then reran the complete relevant unit scenario and typecheck/lint. Final logs contain the passing outcomes.

## BDD remap for parent documentation

- PA-076 and PA-080 retired: removed their obsolete tags and row/limit/traversal scenarios.
- PA-094: `PartnerActivityPage.entry.test.tsx` opening scenario (also PA-075); `MeetingEntryDialog.keys.test.tsx` native newline and IME variants; `MeetingEditDialog.test.tsx` native newline variants.
- PA-075: permissions/default initial fields retained, obsolete add/delete control expectations replaced with absence.
- PA-077: partner list/filter/navigation retained; cross-row independence removed with multirow feature.
- PA-078/079: unchanged exact-match and partner/date keyboard behavior.
- PA-081: first test renamed to `saves one meeting, closes the dialog and shows the saved count and list entry`; removed multirow blank-skip scenario; author/multiline, reopen, payload, no Deal link cases retained.
- PA-082: removed extra empty row date scenario; blank initial state remains; partial entry now checks both missing date/content errors and first-invalid-field focus.
- PA-083: single first item partner rejection retains entered content, focus, and unchanged persisted total; unlocated 403 remains.
- PA-084: removed duplicate added-empty-row cancellation scenario; initial empty cancel/Escape and unsaved continue/discard retained.
- PA-085: old Enter-to-Save focus case moved to PA-094; explicit Save test now includes Enter and Shift+Enter multiline content. Other edit behavior retained.
- PA-086: unchanged.

## Self-review

Each edited module retains one responsibility: new-entry dialog, edit dialog, shared entry fields, validation/conversion, or matching behavioral tests/helper. No new untrusted-data boundary, tagged-union branch, assertion escape hatch, logger, dependency, or single-caller abstraction was introduced. Both dialog consumers use the shared native textarea behavior. All changed files are below 200 nonblank/non-line-comment lines. Existing unrelated work was left untouched. Real-browser layout/height evidence is the parent's separate QA responsibility; this worker does not claim to have performed it.

## Parent-requested source identity revalidation

Parent observed an intermediate focus-prop snapshot. Current bytes at line 117 are `focusField={focus}` and line 42 uses `EntryField | null`; no further source change was necessary. Source mtime 09:32:21 preceded original passing typecheck log mtime 09:32:31. Revalidation (09:34:26) reran the same relevant 14-file / 210-test command and `tsc --noEmit`, both exit 0; existing unit/type logs now record this latest run. Before/after SHA-256 receipts in `revalidation-before.json` and `revalidation-after.json` match: `e5a241c488c386b480f707c8435234cca6629d34fb044a43067dbae907398dec`. No source or documentation edits were made during revalidation.
