"""Tools used by the OpsMind investigation graph.

Incident-specific telemetry tools will be added in a later phase.
"""

from langchain_core.tools.base import BaseTool

tools: list[BaseTool] = []