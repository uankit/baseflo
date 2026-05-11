"""SSE event publishing + subscribing.

Per docs/40-features/JOBS-AND-SSE.md §3.4. The persistence path:

  publisher.emit(...)
      ├── INSERT INTO conversation_events (id, conversation_id, sequence, ...)
      └── DB trigger fires NOTIFY conversation_<id>, '<sequence>'

  subscriber.subscribe(conversation_id, last_sequence=N)
      ├── replay rows from DB where sequence > N
      ├── LISTEN conversation_<id>
      └── stream new rows as NOTIFY arrives
"""
