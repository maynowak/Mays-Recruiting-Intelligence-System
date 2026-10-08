# RIS-EXTERNAL-SOURCES-CONTROLLED-UPDATE-01

## Execution timestamp
2026-10-08

## Canonical paths
installer/projects/mays_jobsearch
installer/projects/mays_orders

## Upstream verification
mays_jobsearch remote git@github.com:maynowak/mays-jobsearch.git
Old pin: 3cd58b81483b4cc8969fc5186a0caf3122a28bfb
New upstream main: 29d8b730bb0660d48d1ba774c773e88d9aa7142e

mays_orders remote git@github.com:maynowak/mays-order-aws.git
Old pin: 9c61237185d202e072b2304355ee836154368846
Upstream main: 9c61237185d202e072b2304355ee836154368846
No change.

## Change analysis jobsearch
Commits 3cd58b8..29d8b73:
- API changes: api/_lib/ats.mjs deduplication of requirements; api/_lib/sources/theirstack.mjs RESULTS_LIMIT 40→25
- No endpoint signature changes
- No schema changes
- UI/landing jobstream changes, documentation updates
API compatibility: PRESERVED
Module compatibility: PRESERVED
RIS adapter impact: NONE
Orders worker impact: N/A

## Compatibility gates
- No breaking API contracts
- No schema changes
- RIS agents encapsulate Jobsearch via adapter pattern; changes are internal
- Test regression: 1209 passed, 0 failed

## Controlled update performed
mays_jobsearch checked out to detached HEAD 29d8b730bb0660d48d1ba774c773e88d9aa7142e
Pinned JSON updated installer/mays-jobsearch-clone.pinned.json
mays_orders unchanged, pin remains 9c61237185d202e072b2304355ee836154368846

## Evidence verifier
VERIFIED

## Pin verification
installer/mays-jobsearch-clone.pinned.json matches checkout HEAD
installer/mays-orders-clone.pinned.json matches checkout HEAD
