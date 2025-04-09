# NBA Analytics Agent - Project Memory Bank

## Overview
A full-stack AI-powered NBA analytics platform combining:
- **Backend:** FastAPI + Gemini 2.0 AI agent + nba_api data tools
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui
- **Communication:** Real-time Server-Sent Events (SSE) for streaming responses

---

## Backend (Python FastAPI)

### Core Components
- **config.py:** Centralized environment variables, constants, error messages
- **agents.py:** Defines a single Gemini-powered NBA expert agent with tools
- **tools.py:** Agno `@tool` wrappers exposing NBA data functions
- **api_tools/**
  - **player_tools.py:** Player info, game logs, career stats, awards
  - **game_tools.py:** League game finder, box scores, play-by-play
  - **league_tools.py:** Standings, scoreboard, draft history, league leaders
- **routes/**
  - **analyze.py:** POST `/analyze` endpoint for AI-driven data analysis
  - **sse.py:** GET `/ask` endpoint streaming agent responses via SSE
- **teams.py:** Alias for the single NBA agent (legacy compatibility)
- **README.md:** Setup and testing instructions

### Data Capabilities
- Player search, info, stats, awards
- Team info, rosters
- Game search, box scores, play-by-play
- League standings, leaders
- Draft history

### AI Integration
- Uses Gemini 2.0 Flash model
- Agent equipped with all NBA data tools
- Maintains chat history for context
- Performs retrieval-augmented generation

---

## Frontend (Next.js + TypeScript)

### Structure
- **app/**
  - **layout.tsx:** Sidebar + header layout
  - **page.tsx:** Main chat dashboard with prompt input, progress, chat history
  - **games/, players/, teams/, shot-charts/:** Feature pages (WIP)
- **components/**
  - **agent/**
    - **InitialChatScreen.tsx:** Example prompts, capabilities, limitations
    - **PromptInputForm.tsx:** User input form
    - **ChatMessageDisplay.tsx:** Chat message renderer
    - **ErrorDisplay.tsx:** Error message display
  - **ui/:** shadcn/ui components (Button, ScrollArea, Avatar, etc.)
  - **layout/SidebarNav.tsx:** Sidebar navigation links
- **lib/hooks/useAgentChatSSE.ts:** Custom hook for SSE chat streaming
- **globals.css:** Tailwind CSS styles
- **next.config.ts, tsconfig.json, package.json:** Config files

### Features
- Real-time chat with AI agent
- Streaming progress updates
- Example prompts for NBA queries
- Displays capabilities and limitations
- Handles errors gracefully

---

## Data Flow

1. User enters or clicks an example prompt
2. Frontend sends prompt to backend `/ask` endpoint via SSE
3. Backend NBA agent streams intermediate and final responses
4. Frontend updates progress, chat history, and displays results live
5. Backend tools fetch NBA data as needed, AI analyzes and responds

---

## Technologies

- **Backend:** FastAPI, Agno, Gemini 2.0, nba_api, Python
- **Frontend:** Next.js (App Router), React, TypeScript, Tailwind CSS, shadcn/ui
- **Streaming:** Server-Sent Events (SSE)
- **Testing:** pytest, manual scripts
- **Storage:** SQLite (for agent history)

---

## Summary

This project provides a sophisticated, AI-powered NBA analytics platform with:
- Rich NBA data retrieval
- AI-driven analysis and summarization
- Real-time interactive chat interface
- Modular, well-structured codebase ready for extension