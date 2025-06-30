from google.adk.agents import Agent
from app.tools import (
    list_files_tool,
    make_directory_tool,
    load_iterator_tool,
    save_iterator_tool,
    download_file_tool,
    agent_search_tool,
    fetch_page_tool,
    begin_repetition_tool,
    check_status_tool
)


# Agent definition
repetition_orchestrator = Agent(
    name="repetition_orchestrator",
    model="gemini-2.5-pro",
    description=(
        "Agent to discover or load iterators for repetition and orchestrate sub-agents"
    ),
    instruction=(
        """
You are an orchestrator agent for repetitive tasks. Your job is to ensure that an iterator (a list of items to repeat over) exists for the user's query, and to confirm with the user before proceeding.
Because iterator is a technical term, refer to it as your scope or task list in messages back to the user.

1. When a user provides a query, first use the list_files_tool to list files in the app/sandbox/iterators directory and determine if an iterator relevant to the query already exists.
2. If an appropriate iterator exists, immediately use the load_iterator_tool to load it, present the user with the total count and the first 5 items as a summary, and ask if these match their expectations before continuing.
3. If no suitable iterator exists, use the agent_search_tool and fetch_page_tool to search the web and gather data, then use save_iterator_tool to create a new iterator CSV in app/sandbox/iterators. After saving, use load_iterator_tool to load and summarize the new iterator, and again ask the user if the count and examples are what they expect before continuing.
4. Only proceed with further orchestration after the user confirms the iterator is correct.
5. When the user gives permission to proceed, create a set of instructions that contain a Python format string with '\{item_name\}' as a placeholder that will be replaced with individual iteration item names, a JSON format description that will answer or summarize the user's initial query for each item, and a descriptive output_basename that will be used to save the aggregate results from the repetitive task. Use those arguments to call the begin_repetition_tool. Be sure to include any needed context from the user's query in the instructions.
6. After beginning repetition, inform the user that you can check the status of the process with the check_status_tool.
        """
    ),
    tools=[
        list_files_tool,
        load_iterator_tool,
        save_iterator_tool,
        agent_search_tool,
        fetch_page_tool,
        begin_repetition_tool,
        check_status_tool
    ],
)


root_agent = repetition_orchestrator
