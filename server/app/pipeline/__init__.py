"""Baseflo build pipeline — artifact-centric workspace generation.

The pipeline replaces the monolithic 8-stage pydantic_graph with an explicit
4-agent DAG that produces versioned artifacts at each step.
"""

from app.pipeline.build import BuildPipeline, BuildRequest, BuildResult

__all__ = ["BuildPipeline", "BuildRequest", "BuildResult"]
