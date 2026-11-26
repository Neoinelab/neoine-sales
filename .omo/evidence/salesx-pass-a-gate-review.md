# salesX Pass A review

recommendation: APPROVE
visualVerdict: PASS
confidence: MEDIUM
blockers: []

originalIntent: Replace the authenticated upper-left NEOINE 영업관리 text with images/salesX.png.
desiredOutcome: A loaded salesX image with an accessible name remains a home link in the existing responsive header.
userOutcomeReview: The current Layout imports the requested asset and renders it as an img named salesX within href="/". All four after captures visibly show the logo. Existing menu and page content remain present. Approval is bounded to the logo replacement, not a whole-application accessibility certification.

## Checked artifacts

- frontend/src/shared/ui/Layout.tsx:7,29-33 (asset, image, home link)
- frontend/src/index.css:78-85 (focus, existing header tokens, image sizing and expanded pointer area)
- frontend/src/shared/ui/Layout.menu.test.tsx:18-30
- docs/features/platform-common.md:129,660-663 (PL-R34, PL-073)
- artifacts/qa/salesx-browser.mjs
- All eight artifacts/qa/salesx-{desktop-1440,iphone-14}-{light,dark}-{before,after}.png, directly opened
- artifacts/qa/salesx-iphone-14-dark-detect.json

## G-J checklist, scoped to the changed logo

| Item | Verdict | Evidence/reason |
| --- | --- | --- |
| G1 | N/A | Static logo; no animation in Layout or logo styles. |
| G2 | N/A | No motion or geometry transition added. |
| G3 | N/A | No animation gates input. |
| G4 | N/A | No motion added. |
| G5 | PASS | Native anchor activation; no asynchronous logo interaction handler. |
| G6 | NOTE | Loaded captures are stable, but no cold-load sequence proves absence of transient horizontal shift; img has CSS height and auto width without intrinsic dimensions. No demonstrated criterion failure. |
| G7 | PASS | Static PNG, no flashing code. |
| H1 | N/A | No new data view or request state. |
| H2 | N/A | No new loading UI. |
| H3 | N/A | No new operation feedback. |
| H4 | N/A | No new alert. |
| H5 | NOTE | Existing native anchor and global focus style retained; hover/pressed capture not supplied. No disabled logo state. |
| H6 | N/A | No sheet/modal modification. Reported draft guard issue is outside logo contract. |
| H7 | N/A | No long operation. |
| H8 | N/A | No permission prompt. |
| H9 | N/A | Authentication flow untouched. |
| H10 | N/A | Search outside changed header brand. |
| H11 | N/A | Settings untouched. |
| I1 | PASS | Native first header anchor; global :focus-visible outline (index.css:78); no programmatic focus modification. Source trace, no focused capture supplied. |
| I2 | PASS | Native anchor Enter behavior; logo introduces no menu or shortcut override. Existing menu Escape behavior is not changed or certified here. |
| I3 | PASS | Image alt="salesX" supplies image/link name; header, nav label, main retained. |
| I4 | N/A | No gesture-only action. |
| I5 | N/A | No media. |
| J1 | N/A | Web application, no native macOS chrome change. |
| J2 | PASS | Phone after captures show logo fits alongside existing menu control; no new compact popover, title, or input. |

## Direct programming and remove-ai-slops pass

Read both skills and TypeScript/testing references. The implementation uses the real shared component tree and an imported asset, not a screenshot substitute. No new parsing, normalization, abstraction, assertion escape hatch, dependency, or test-only production seam appears in the inspected logo implementation. Styling reuses existing header tokens and logo classes.

PL-073 test: R (retain). It checks the accessible rendered image and actual link destination at the existing application test boundary. The negative old-copy assertion accompanies positive image/link assertions; it is not deletion-only, tautological, source-grep, mock echo, copied inventory, or an implementation-mirroring private-call assertion. It would catch an absent accessible logo or wrong home destination. It does not prove image bytes load; the actual after captures supply that evidence. No excessive case multiplication found. No source mutations or test edits performed.

## Evidence gaps and nonblocking notes

- All before captures show a broken image named 사이트 로고, rather than the original requested NEOINE 영업관리 text. They establish only the captured broken-image baseline. Do not describe them as proof of the original text baseline.
- Phone before/after controls differ in darkness independently of the logo; the browser script captures immediately after changing emulated theme without a transition-settling check. The snapshots do not prove unrelated styling changed in production.
- Existing page/nav contrast problems are visible in both dark captures and the detector report. No contrast regression caused by replacing the logo is demonstrated.
- The stated 35 tests, typecheck/build, naturalWidth probe, and draft-guard reproduction were not reproduced in this read-only visual pass; no raw command output artifact was provided. No full diff, separate code-review report, or notepad was supplied. My direct bounded slop pass supports this review without claiming those independent runs.
- No live keyboard activation, cold asset-load sequence, or focused-state screenshot was supplied; source supports the native anchor contract.
- ulw-loop status returned ULW_LOOP_PLAN_MISSING; report uses the fallback evidence directory.
