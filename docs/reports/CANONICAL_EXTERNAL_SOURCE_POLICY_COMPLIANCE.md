# Canonical External Source Policy Compliance

## Policy
RIS must use only installer/projects/mays_jobsearch and installer/projects/mays_orders as authoritative external sources.

## Verification
mays_jobsearch pinned commit 3cd58b81483b4cc8969fc5186a0caf3122a28bfb
Remote git@github.com:maynowak/mays-jobsearch.git main

mays_orders pinned commit 9c61237185d202e072b2304355ee836154368846
Remote git@github.com:maynowak/mays-order-aws.git main

## Previous Analysis Correction
Previous RIS-PRODUCT-VISION-FUNCTIONAL-GAP-ANALYSIS-01 used sibling development directories:
- /home/dci-student/projects/Mays-Jobsearch-featurework/mays-jobsearch
- /home/dci-student/projects/Mays-Orders-AWS

These are not authorized per policy.

## Canonical Source Summary

mays_jobsearch provides:
- api/profile.mjs, api/match.mjs, api/jobs.mjs, api/cover-letter.mjs, api/alerts.mjs
- Browser-side CV extraction, model selection, job sources integration
- Domain logic owned by Jobsearch

mays_orders provides:
- lambda/src/index.py, order_service.py, sqs_handler.py, state_machine.py
- API GET/POST/PATCH /orders
- Order lifecycle with SQS worker
- Domain logic owned by Orders

RIS must encapsulate via agents/adapters, not duplicate or modify external source code.

Compliance confirmed.
