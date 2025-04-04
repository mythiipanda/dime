## Current Objective

Define initial Agno agents and workflows for the NBA Analytics backend.

## Context

The basic Python project structure (`nba-analytics-backend`) is set up with a virtual environment and core dependencies (Agno, FastAPI, etc.). The focus has shifted from frontend layout to backend agent definition based on user feedback.

## Next Steps

1.  **Review Requirements:** Re-examine `productContext.md` to identify the core backend functionalities needed (data aggregation, normalization, analysis).
2.  **Define Agent Roles:** Flesh out the conceptual agents in `agents.py`:
    *   `DataAggregatorAgent`: Define its purpose (fetch from specific APIs like BallDontLie), potential tools (HTTP request tool, maybe a custom tool for API key handling), and instructions.
    *   `DataNormalizerAgent`: Define its purpose (transform raw API data into a standard schema), inputs/outputs, and instructions. Might not need external tools initially.
    *   `AnalysisAgent`: Refine its purpose (generate insights from normalized data), configure the Gemini model, and define instructions for analysis types (e.g., team comparison, player trends).
3.  **Outline Workflow:** Conceptualize a simple workflow in `agents.py` (or a new `workflows.py`) showing how these agents might interact (e.g., Aggregator -> Normalizer -> Analyzer). Use comments initially.
4.  **Refine FastAPI (`main.py`):** Update the placeholder endpoints in `main.py` to reflect potential interactions with the defined agents/workflows (e.g., an endpoint to trigger analysis for a specific team).
5.  **Update Documentation:** Update `systemPatterns.md` with the initial agent/workflow design. Update `progress.md` and `projectRoadmap.md`. Prepare the next `currentTask.md`.