# System Patterns: NBA Sports Analytics Platform

## Frontend Setup & Architecture

*   **Project Initialization:** Uses `npx create-next-app@latest` for scaffolding the Next.js project.
    *   Configuration: TypeScript, Tailwind CSS, App Router, ESLint.
*   **UI Component Integration:** Uses `npx shadcn-ui@latest init` to integrate shadcn/ui with the Next.js project.
    *   Configures `tailwind.config.ts`, `globals.css`, and utility functions.
    *   Sets up import alias `@/*` via `tsconfig.json` (or `jsconfig.json`).
*   **Component Management:** Uses `npx shadcn-ui@latest add [component]` to add individual UI components and their dependencies. Components are added directly to the codebase (e.g., in a `components/ui` directory) allowing for customization.
*   **Routing:** Leverages Next.js App Router for file-system based routing, layouts, and server/client component architecture.
*   **Styling:** Primarily uses Tailwind CSS utility classes, configured via `tailwind.config.ts`. shadcn/ui components are built with Tailwind. CSS Variables are used for theming (light/dark mode).
*   **Theming:** Dark mode support implemented via `ThemeProvider` component (from shadcn/ui docs or similar) managing CSS variables and local storage persistence.

## Backend Setup & Architecture (Agno)

*   **Project Initialization:** Standard Python project setup (`mkdir`, `python -m venv .venv`, `pip install ...`). No specific Agno CLI command for project scaffolding identified.
*   **Core Components:**
    *   **Agents (`agents.py`):** Define individual agents (`agno.agent.Agent`) with specific roles, models (e.g., `agno.models.google.Gemini`), tools, instructions, and potentially memory/knowledge.
        *   `DataAggregatorAgent`: Fetches raw data from external APIs (requires HTTP tools).
        *   `DataNormalizerAgent`: Transforms raw data into a standard schema.
        *   `AnalysisAgent`: Interprets normalized data using an LLM (Gemini).
    *   **API Server (`main.py`):** Uses FastAPI to expose endpoints for interacting with agents or workflows.
    *   **Workflows (Planned):** Define stateful, multi-agent processes using Python classes inheriting from `agno.workflow.Workflow` to orchestrate agent interactions (e.g., Fetch -> Normalize -> Analyze).
*   **Storage:** Uses `agno.storage.agent.SqliteAgentStorage` (or other `AgentStorage` subclasses) for persisting agent session data locally during development.
*   **Configuration:** Uses `.env` file for managing API keys and other secrets (`python-dotenv`).
*   **Dependencies:** Managed via `pip` and listed in `requirements.txt`.

## Data Handling (Revised Plan)

*   **Data Flow:** Frontend -> Backend API (FastAPI) -> Agno Workflow/Agents -> External APIs -> Agents -> Backend API -> Frontend.
*   **Aggregation:** `DataAggregatorAgent` fetches data from NBA APIs.
*   **Normalization:** `DataNormalizerAgent` transforms data into a consistent project schema.
*   **Caching:** Will be implemented within the backend, potentially at the Agno agent/tool level or using FastAPI utilities, to manage API rate limits and improve performance.

## AI Integration (Planned)

*   **Backend Processing:** The `AnalysisAgent` (using Gemini via `agno.models.google.Gemini`) will run on the server, receiving normalized data and generating insights.
*   **Prompt Engineering:** Focus on designing effective prompts for the `AnalysisAgent` to interpret statistical data and generate meaningful text summaries or predictions based on user requests.

## Code Structure

*   **Monorepo Structure (Implicit):** Separate directories for frontend (`nba-analytics-frontend`) and backend (`nba-analytics-backend`).
*   **Frontend:** Standard Next.js App Router structure.
*   **Backend:** Standard Python project structure with `main.py`, `agents.py`, `.venv`, `requirements.txt`.