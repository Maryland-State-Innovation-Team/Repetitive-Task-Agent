# Repetitive-Task-Agent
A Google ADK implementation of an agent orchestrated by repetitive task lists.

## Overview

This project provides an orchestrator agent that automates repetitive tasks over a list of items (a "task list" or "scope"). The agent can discover, load, or create task lists, confirm them with the user, and then execute a sub-agent for each item in the task list, collecting structured results.

## Features

- **Task List Management**: Automatically discovers or creates task lists from CSV files or web data.
- **User Confirmation**: Summarizes the task list and asks for user confirmation before proceeding.
- **Repetitive Task Execution**: Orchestrates sub-agents to process each item in the task list using user-provided instructions and response formats.
- **Tooling**: Includes tools for file management, directory creation, file download, web search, page fetching, and progress checking.
- **Result Aggregation**: Collects results from each iteration and saves them as a CSV file.

## How It Works

1. **Task List Discovery/Creation**:  
   The orchestrator agent checks for existing task lists in `app/sandbox/task_lists`. If none match the user's query, it can search the web and create a new task list.
2. **User Confirmation**:  
   The agent summarizes the task list (total count and sample items) and asks the user to confirm before proceeding.
3. **Task Execution**:  
   Upon confirmation, the agent uses a sub-agent to process each item in the task list according to user instructions and a specified JSON response format.
4. **Progress Tracking**:  
   The agent provides tools to check the status of the ongoing repetitive task.
5. **Result Output**:  
   Results are saved as a CSV in `app/sandbox/results`.

## Example

### Example Query

```
Find the official government website for every county in Maryland.
```

### Sample Agent Flow

1. **Task List Discovery**:  
   The agent checks for a predefined task list in `app/sandbox/task_lists/maryland_counties.csv` containing the list of all Maryland counties.

2. **User Confirmation**:  
   The agent loads the task list, summarizes it (e.g., "24 items found: Allegany, Anne Arundel, Baltimore, ..."), and asks the user to confirm that this matches their expectations before proceeding.

3. **Prompt Template Creation**:  
   Once confirmed, the agent creates a prompt template for the sub-agent:
   
   > "Find the official government website for the county named '{item_name}' in Maryland. Return a JSON object with keys 'county' and 'official_website'."

4. **Sub-Agent Execution**:  
   For each county, the sub-agent receives a prompt with the county name substituted for `{item_name}` and returns a structured JSON result. This is repeated for every county in the task list.

5. **Result Aggregation**:  
   The orchestrator collects all results and saves them as a CSV file in `app/sandbox/results/maryland_county_websites.csv`.

**Scaling Technique:**  
This approach allows the system to scale to any number of tasks, as each sub-agent only processes one item at a time. No single LLM ever needs to process all results within one context window, enabling comprehensive and efficient output even for large datasets.

## Usage

### 1. Setup

- Copy the example environment file:
  ```
  cp app/.env-example app/.env
  ```
- From the root directory, launch the development UI:
  ```
  adk web
  ```
  This will start a UI on port 8000.

### 2. Workflow

- Interact with the orchestrator agent via the UI.
- Provide a query describing your repetitive task.
- Confirm the task list (scope) when prompted.
- Specify instructions and response format for each item.
- Monitor progress and download results when complete.

## File Structure

- `app/agent.py`: Defines the orchestrator agent and its workflow.
- `app/tools.py`: Implements tools for file operations, task list management, downloading, web search, and repetitive task orchestration.
- `app/sandbox/task_lists/`: Stores task list CSV files.
- `app/sandbox/results/`: Stores result CSV files.

## Requirements

- Python 3.10+
- Google ADK and dependencies (see `requirements.txt`)
