# Project Overview

This project is a multi-agent data analysis platform built with:

- Agent Framework: Google ADK
- Tool Server: FastMCP
- Backend API: FastAPI + SQLite
- Frontend: React

The system allows users to interact with an orchestrator agent via chat, which dynamically utilizes MCP tools for data analysis, EDA, and visualization.

---

# Architecture

## Components

### 1. adk_backend (Google ADK)

- Root Agent (Orchestrator)
- Sub Agents (EDA, Visualization, Data Retrieval)
- Responsible for:
  - Task planning
  - Tool selection
  - MCP tool invocation
  - Multi-agent orchestration

### 2. mcp_server (FastMCP)

- Provides tools for:
  - Data preprocessing
  - EDA (summary stats, correlation, etc.)
  - Visualization (Plotly, charts)
- Stateless tool execution layer

### 3. web_backend (FastAPI + SQLite)

- Acts as BFF (Backend For Frontend)
- Responsibilities:
  - Session management
  - Agent API proxy
  - Artifact serving (CSV, images, plots)
  - State parsing (for frontend rendering)

### 4. web_front (React)

- Chat UI for interacting with agents
- Dynamic UI rendering:
  - Tables (CSV)
  - Charts (Plotly JSON)
  - Forms (dropdown, checkbox)

---

# Agent Design Principles

## 1. Orchestrator Pattern

- Root agent NEVER performs heavy computation
- Always delegates to sub-agents or tools

## 2. Tool-first Design

- All data operations MUST be done via MCP tools
- Agents should not implement business logic directly

## 3. Stateless Agents

- Agent state must be minimal
- Use external storage (SQLite / artifacts) for persistence

## 4. Explicit Output Schema

- Every tool and sub-agent must define output schema
- Prefer structured JSON over plain text

---

# MCP Tool Guidelines

## Tool Categories

- data_preprocessing_toolbox
- eda_toolbox
- visualization_toolbox
- modeling_toolbox (optional)

## Rules

- Tools must be deterministic
- Tools must NOT depend on agent state
- Tools must return structured outputs:
  ```json
  {
    "status": "success",
    "outputs": [...]
  }
  ```
