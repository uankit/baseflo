"""Orchestration: jobs, sagas, and event streaming.

Per docs/40-features/JOBS-AND-SSE.md, generation work runs in arq workers, not
on the API thread. Events are persisted with monotonic per-conversation
sequences and broadcast via Postgres LISTEN/NOTIFY for live SSE streaming.
"""
