recommendation: APPROVE
visualVerdict: PASS
confidence: MEDIUM
blockers: []
originalIntent: Replace authenticated upper-left NEOINE 영업관리 branding with images/salesX.png.
desiredOutcome: Visible salesX wordmark, old brand absent, preserved header/layout/body sizing and mobile fit in both themes.
userOutcomeReview: All four after captures visibly show salesX at the upper left, without old brand text or broken image. Header/content geometry remains consistent. The dark wordmark's lower purple gradient is less distinct but the word is readable; no opaque image rectangle appears. The required supplied asset is used directly.

Checked artifacts:
- frontend/src/shared/ui/Layout.tsx
- frontend/src/index.css
- artifacts/qa/salesx-browser.mjs
- artifacts/qa/salesx-desktop-1440-light-before.png
- artifacts/qa/salesx-desktop-1440-light-after.png
- artifacts/qa/salesx-desktop-1440-dark-before.png
- artifacts/qa/salesx-desktop-1440-dark-after.png
- artifacts/qa/salesx-iphone-14-light-before.png
- artifacts/qa/salesx-iphone-14-light-after.png
- artifacts/qa/salesx-iphone-14-dark-before.png
- artifacts/qa/salesx-iphone-14-dark-after.png

A — Layout: PASS for changed region. Header remains aligned; mobile logo and toggle have ample separation and no clipping. Desktop navigation moves modestly right to accommodate the valid image. Main content positions are unchanged. A9 whole-page table overflow is pre-existing and locally clipped/scrollable; snapshots do not establish scroll interaction. A12 scroll-owner evidence was not supplied.
B — Hierarchy: PASS for scope. Wordmark is subordinate to page content, title and actions remain intact. No additional decorative branding.
C — Text: PASS for scope. Source retains --font-base:14px and body use of this token. Image alt is salesX. Korean labels remain intact. Pre-existing mobile explanation wraps 마지막 '다' onto a new line in both before/after (C5 follow-up, not caused by logo).
D — Targets: PASS by source for new logo. 32px image with pseudo-element inset -6px vertically provides a 44px target. Other controls retain prior geometry. Actual pointer hit-testing not reproduced in this pass.
E — Themes: PASS for logo visibility; full-page E2 fails pre-existing dark navigation/table contrast. Dark gradient is less distinct but legible; user-provided brand asset should not be redesigned on taste grounds. Theme follows prefers-color-scheme. No opaque background fill.
F — Consistency: PASS for shared-header implementation and required branding. Same imported asset and CSS apply to both viewport classes. Existing active-nav underline is unchanged, not a new failure. Other authenticated routes were not separately captured in this visual pass.

Evidence notes (not blockers to the requested replacement):
- Every before capture contains a broken image with alt text 사이트 로고, not original NEOINE 영업관리 text. These prove repair/layout continuity from the captured state, not original-text baseline fidelity.
- Controls differ in color between captures. The script changes media and immediately captures without waiting for style transitions to settle. Exact whole-page color fidelity cannot be claimed from these pairs.
- Browser measurements (2172 natural width, 32px rendered image height, 56px header, no document overflow) were supplied by parent; measurement code inspected, but no raw persisted measurement receipt was available to reproduce those numeric claims here.
- No 1920, scrolled-end, long-label, or 200% zoom captures supplied. These are evidence scope limits, not demonstrated failures of this small image replacement.

Programming/remove-ai-slops perspective: consulted both skills and TypeScript reference. Direct source inspection finds a simple static image import and semantic img, no production parsing, normalization, extraction, defensive framework, or test-only seam. No test changes or full diff were supplied to this visual pass; no claim of auditing unseen tests. No code-review report for this task exists in the current evidence directory, so independent report coverage cannot be confirmed. The direct source pass supports completion of this limited visual task. Existing unused brand text CSS is a cleanup note only.

No production files edited, no broad tests run. ULW status reported ULW_LOOP_PLAN_MISSING; fallback report path used.
