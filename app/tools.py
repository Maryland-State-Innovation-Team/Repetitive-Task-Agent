import os
import time
import shutil
import pandas as pd
import requests
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import agent_tool, FunctionTool, LongRunningFunctionTool, ToolContext
from google.adk.tools.google_search_tool import google_search
import google.genai.types as types
import logging
import urllib.request
import json
from app.utils import extract_json_from_model_output
import asyncio


logger = logging.getLogger(__name__)


SANDBOX_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "sandbox"))


def is_within_sandbox(path: str) -> bool:
    """Checks if the given path is within the app/sandbox directory."""
    abs_path = os.path.abspath(path)
    return abs_path.startswith(SANDBOX_ROOT)


def list_files(file_path: str) -> dict:
    """Lists files in a directory within app/sandbox.

    Args:
        file_path (str): The directory path to list files from.
    Returns:
        dict: A dictionary with 'status' ('success' or 'error'). On success, includes 'files' (list of filenames). On error, includes 'error_message'.
    """
    abs_path = os.path.abspath(file_path)
    if not is_within_sandbox(abs_path):
        return {"status": "error", "error_message": "Path is outside of app/sandbox."}
    if not os.path.exists(abs_path):
        return {"status": "error", "error_message": "Path does not exist."}
    if not os.path.isdir(abs_path):
        return {"status": "error", "error_message": "Path is not a directory."}
    return {"status": "success", "files": os.listdir(abs_path)}


def list_existing_task_lists() -> dict:
    """Lists existing task list files in app/sandbox/task_lists.

    Returns:
        dict: A dictionary with 'status' ('success' or 'error'). On success, includes 'files' (list of filenames). On error, includes 'error_message'.
    """
    task_list_dir = os.path.join(SANDBOX_ROOT, "task_lists")
    abs_path = os.path.abspath(task_list_dir)
    if not is_within_sandbox(abs_path):
        return {"status": "error", "error_message": "Path is outside of app/sandbox."}
    if not os.path.exists(abs_path):
        return {"status": "error", "error_message": "Path does not exist."}
    if not os.path.isdir(abs_path):
        return {"status": "error", "error_message": "Path is not a directory."}
    return {"status": "success", "files": os.listdir(abs_path)}


def make_directory(file_path: str) -> dict:
    """Creates a directory within app/sandbox.

    Args:
        file_path (str): The directory path to create.
    Returns:
        dict: A dictionary with 'status' ('success' or 'error'). On success, includes 'message'. On error, includes 'error_message'.
    """
    abs_path = os.path.abspath(file_path)
    if not is_within_sandbox(abs_path):
        return {"status": "error", "error_message": "Path is outside of app/sandbox."}
    try:
        os.makedirs(abs_path, exist_ok=True)
        return {"status": "success", "message": f"Directory created: {abs_path}"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


async def load_task_list(csv_path: str, tool_context: ToolContext) -> dict:
    """
    Loads a CSV, serializes its first column to JSON, saves it as an 
    artifact, stores the artifact's filename in the session state, and returns a summary.

    Args:
        csv_path (str): The path to the CSV file within app/sandbox.

    Returns:
        dict: A dictionary with 'status' ('success' or 'error'). On success, 
              includes 'message' and 'summary'. On error, includes 'error_message'.
    """
    abs_path = os.path.abspath(csv_path)
    if not is_within_sandbox(abs_path):
        return {"status": "error", "error_message": "CSV path is outside of app/sandbox."}
    if not os.path.exists(abs_path):
        return {"status": "error", "error_message": "CSV file does not exist."}
    
    try:
        df = pd.read_csv(abs_path)
        if df.shape[1] == 0:
            return {"status": "error", "error_message": "CSV has no columns."}
        
        first_col_list = df.iloc[:, 0].tolist()
        
        # 1. Serialize the list to JSON
        iterator_json = json.dumps(first_col_list)
        
        # 2. Package the data into a Part with the correct MIME type
        iterator_artifact = types.Part(
            text=iterator_json
        )
        
        filename = "session_iterator.json"

        # 3. Save the artifact asynchronously
        version = await tool_context.save_artifact(filename=filename, artifact=iterator_artifact)
        
        # 4. Store the filename in the state. We don't need to store the version
        #    if we always want to load the latest.
        tool_context.state['iterator_filename'] = filename
        
        logger.info(f"Successfully saved artifact '{filename}' as version {version}.")

        summary = {
            "total_items": len(first_col_list),
            "preview": first_col_list[:5]
        }
        logger.info(f"Summary: {summary}")
        return {
            "status": "success",
            "message": f"Task list saved as artifact '{filename}' (version {version}).",
            "summary": summary
        }
        
    except ValueError as e:
        logger.error(f"Error saving artifact: {e}. Is ArtifactService configured in Runner?")
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        logger.error(f"An unexpected error occurred during artifact save: {e}")
        return {"status": "error", "error_message": str(e)}


def save_task_list(strings: list[str], basename: str) -> dict:
    """
    Saves a list of strings as a single-column CSV in app/sandbox/task_lists with a header 'name'.

    Args:
        strings (list[str]): The list of strings to save.
        basename (str): The base filename (without extension) for the CSV file.
    Returns:
        dict: A dictionary with 'status' ('success' or 'error'). On success, includes 'csv_path'. On error, includes 'error_message'.
    """
    task_list_dir = os.path.join(SANDBOX_ROOT, "task_lists")
    os.makedirs(task_list_dir, exist_ok=True)
    csv_path = os.path.join(task_list_dir, f"{basename}.csv")
    if not is_within_sandbox(csv_path):
        return {"status": "error", "error_message": "Output path is outside of app/sandbox."}
    if os.path.exists(csv_path):
        return {"status": "error", "error_message": "A task list with that filename already exists."}
    try:
        df = pd.DataFrame(strings, columns=["name"])
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved task list to {csv_path}")
        return {"status": "success", "csv_path": csv_path}
    except Exception as e:
        logger.error(f"Failed to save task list: {e}")
        return {"status": "error", "error_message": str(e)}


def download_file(source_url: str, out_file_path: str) -> dict:
    """Downloads a file from a URL to a specified path within app/sandbox.

    Args:
        source_url (str): The URL to download the file from.
        out_file_path (str): The output file path within app/sandbox.
    Returns:
        dict: A dictionary with 'status' ('success' or 'error'). On success, includes 'message'. On error, includes 'error_message'.
    """
    abs_path = os.path.abspath(out_file_path)
    if not is_within_sandbox(abs_path):
        return {"status": "error", "error_message": "Output path is outside of app/sandbox."}
    try:
        response = requests.get(source_url, stream=True)
        response.raise_for_status()
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        return {"status": "success", "message": f"File downloaded to {abs_path}"}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def get_webpage_content(url: str) -> dict:
    """Retrieves and returns the content of 'url'.

    Args:
      url: URL to fetch.

    Returns:
      A dict with "status", "page_contents", and (optional) "error_message" keys.
    """
    opener = urllib.request.build_opener()
    opener.addheaders = [("User-Agent", "Mozilla/5.0")]
    urllib.request.install_opener(opener)
    logger.debug("Fetching page: %s", url)
    try:
        page = urllib.request.urlopen(url)
        page_text = page.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        errmsg = "Failed to fetch page %s: %s", url, err
        logger.error(errmsg)
        return {"status": "error", "message": errmsg}
    return {"status": "success", "page_contents": page_text}


search_agent = Agent(
    model='gemini-2.5-flash',
    name='SearchAgent',
    instruction="""
    You're a specialist in Google Search
    """,
    tools=[google_search]
)


def check_task_status(tool_context: ToolContext) -> dict:
    """
    Reports the progress, total number of items, and elapsed seconds for the current repetition task.

    Returns:
        dict: A dictionary with 'progress', 'total', 'elapsed_seconds', 'status', and 'results_path'.
    """
    progress = tool_context.state.get('user:progress', 0)
    total = tool_context.state.get('user:total', 0)
    elapsed_seconds = tool_context.state.get('user:elapsed_seconds', 0)
    task_status = tool_context.state.get('user:repetition_task_status', 'not_started')
    results_path = tool_context.state.get('user:results_path', '')
    return {
        "progress": progress,
        "total": total,
        "elapsed_seconds": elapsed_seconds,
        "status": task_status,
        "results_path": results_path
    }


list_files_tool = FunctionTool(func=list_files)
list_existing_task_lists_tool = FunctionTool(func=list_existing_task_lists)
make_directory_tool = FunctionTool(func=make_directory)
load_task_list_tool = FunctionTool(func=load_task_list)
save_task_list_tool = FunctionTool(func=save_task_list)
download_file_tool = FunctionTool(func=download_file)
get_webpage_content_tool = FunctionTool(func=get_webpage_content)
web_search_tool = agent_tool.AgentTool(agent=search_agent)
check_task_status_tool = FunctionTool(func=check_task_status)


task_agent = Agent(
    name="task_agent",
    model="gemini-2.5-flash",
    description="Agent to execute a single tasks of a repetitive progress using provided instructions and tools.",
    instruction="""
Your purpose is to execute a specific task based on the inputs you receive.

---

### **Inputs You Will Receive**

You will be given three things:
1.  **`Item name`**: The specific item you must process (e.g., a company name, a URL, a product ID).
2.  **`Instructions`**: The precise steps you must follow to gather information about the `item_name`.
3.  **`Response format`**: A JSON schema that you **must** use for your output.

---

### **Your Task**

Your job is to use your available tools to follow the `Instructions` perfectly and generate a single JSON object that matches the `Response format`.

---

### **Critical Output Rules**

Your final output is processed by an automated system, so these rules are not optional.

1.  **JSON Only**: Your final response **must only be the valid JSON object**. Do not add any extra text, explanations, or conversational phrases like "Here is the JSON:". The response must begin with `{` and end with `}`.
2.  **Strictly Adhere to Schema**: The keys in your JSON output must exactly match the keys provided in the `Response format`. Do not add, remove, or rename keys.
3.  **Flat JSON Structure**: The final JSON object **must be flat**. This means there can be no nested objects or arrays. All key-value pairs must be at the top level.

**Example of a valid flat structure:**
`{ "key1": "value1", "key2": "value2", "key3": "value3" }`

**Example of an invalid nested structure:**
`{ "key1": "value1", "details": { "key2": "value2" } }`
""",
    tools=[
        list_files_tool,
        make_directory_tool,
        download_file_tool,
        web_search_tool,
        get_webpage_content_tool
    ]
)


# Async helper function to run the actual repetition loop in the background
async def _run_repetition_loop(
    iterator_list: list[str],
    instructions: str,
    response_format: str,
    output_basename: str,
    tool_context: ToolContext
) -> None:

    # Configuration
    app_name = "SubAgent"
    user_id = tool_context._invocation_context.user_id
    session_service = InMemorySessionService()

    results = []
    start_time = time.time()
    total_items = len(iterator_list)

    tool_context.state['user:total'] = total_items
    tool_context.state['user:progress'] = 0
    tool_context.state['user:elapsed_seconds'] = 0
    tool_context.state['user:repetition_task_status'] = 'running'
    tool_context.state['user:results_path'] = ''

    for idx, item in enumerate(iterator_list):
        # Fill in the prompt template
        formatted_instructions = instructions.format(item_name=item)
        query = f"Item name: {item}\nInstructions: {formatted_instructions}\nResponse format: {response_format}"

        # Start a new session for each subagent
        session = await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
        )
        runner = Runner(
            app_name=app_name,
            agent=task_agent,
            session_service=session_service,
        )
        content = types.Content(role="user", parts=[types.Part(text=query)])
        
        current_events = list(
            runner.run(
                user_id=user_id, session_id=session.id, new_message=content
            )
        )

        # Clean up session
        await session_service.delete_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session.id
        )

        # Fetch last response, parse JSON, and append
        if current_events:
            last_event = current_events[-1]
            final_response = "".join(
                [part.text for part in last_event.content.parts if part.text]
            )
            result = extract_json_from_model_output(final_response)
            if result:
                result['original_item'] = item
                results.append(result)
            else:
                results.append({'original_item': item, 'error': f'Failed to parse JSON: {final_response}'})
        else:
            results.append({'original_item': item, 'error': 'No response from sub-agent'})

        # Update progress in state
        tool_context.state['user:progress'] = idx + 1
        tool_context.state['user:elapsed_seconds'] = int(time.time() - start_time)

    # Save results as CSV after all iterations are complete
    os.makedirs(os.path.join(os.path.dirname(__file__), "sandbox", "results"), exist_ok=True)
    results_path = os.path.join(os.path.dirname(__file__), "sandbox", "results", f"{output_basename}.csv")
    pd.DataFrame(results).to_csv(results_path, index=False)

    tool_context.state['user:repetition_task_status'] = 'completed'
    tool_context.state['user:results_path'] = results_path
    logger.info(f"Repetition task completed. Results saved to {results_path}")


async def execute_task_list(instructions: str, response_format: str, output_basename: str, tool_context: ToolContext) -> dict:
    """
    Orchestrates a repetitive task by iterating over a task list of items, invoking a sub-agent for each item,
    and collecting structured results. The repetitive task runs in the background.

    Args:
        instructions (str): The instruction template for the sub-agent. Should include a Python format string with
            '{item_name}' as a placeholder for the current item.
        response_format (str): A string describing the required JSON schema for the sub-agent's output. This should
            be a flat structure that can be serialized to a CSV (e.g., keys for the item name and any outputs).
        output_basename (str): The base filename (without extension) for the CSV file.

    Returns:
        dict: A dictionary with:
            - 'status': 'success' or 'error'
            - 'message': Indicates task initiation or error.
    """

    # Load iterator
    filename = tool_context.state.get('iterator_filename', 'session_iterator.json')
    artifact = await tool_context.load_artifact(filename=filename)
    if not artifact or not artifact.text:
        return {"status": "error", "error_message": f"Could not load task list artifact '{filename}'."}
    iterator_list = json.loads(artifact.text)

    # Initialize state for progress tracking immediately
    tool_context.state['user:progress'] = 0
    tool_context.state['user:total'] = len(iterator_list)
    tool_context.state['user:elapsed_seconds'] = 0
    tool_context.state['user:repetition_task_status'] = 'initiated'

    # Create a background task to run the actual repetition loop
    asyncio.create_task(
        _run_repetition_loop(iterator_list, instructions, response_format, output_basename, tool_context)
    )

    return {
        "status": "success",
        "message": "Repetitive task initiated in the background. Use check_status to monitor progress."
    }


execute_task_list_tool = LongRunningFunctionTool(func=execute_task_list)
