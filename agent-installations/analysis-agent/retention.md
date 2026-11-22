# Analysis Agent — Retention

Orders, work items, results and audit are retained. Temporary job objects are
deleted after completion or expiry (max 4h). CV bytes are never stored by the
agent; they are fetched from the existing RIS documents bucket for the parser
call only. PURGE is blocked until retention approval and an agent deletion
ledger exist.
