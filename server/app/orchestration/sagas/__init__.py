"""Sagas — long-running multi-step flows with compensating actions.

Per docs/50-design-patterns.md §9. Each saga is a typed sequence of steps
where every step has a forward action and (where applicable) a compensator.
"""
