"""SQLAlchemy 2.x async ORM layer.

Per docs/05-coding-rules.md §3.2, services never import `Session`. Repositories
are the only layer that touches sessions; services receive repositories via DI.
"""
