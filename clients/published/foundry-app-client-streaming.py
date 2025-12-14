"""
Foundry Published Agent Application Client - Streaming Version

This script demonstrates how to interact with a PUBLISHED Agent Application
using the OpenAI SDK with STREAMING responses.

Streaming provides real-time token-by-token output, improving perceived
responsiveness for users.

Key Features:
    - Connects to a published Agent Application endpoint
    - Uses OpenAI SDK with Azure AD authentication
    - STREAMS responses token-by-token as they're generated
    - Maintains conversation history client-side (required for published apps)
    - Interactive multi-turn conversation support

Prerequisites:
    - Azure CLI authenticated (az login)
    - AZURE_AI_FOUNDRY_APP_ENDPOINT set in .env file

Usage:
    python foundry-app-client-streaming.py

Reference:
    https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/publish-agent
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Load environment variables from project root
# Navigate up from clients/published/ to find .env
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")

# =============================================================================
# CONFIGURATION
# =============================================================================

APP_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_APP_ENDPOINT")

if not APP_ENDPOINT:
    print("Error: AZURE_AI_FOUNDRY_APP_ENDPOINT not set in environment")
    print("This should be the published application endpoint URL.")
    print("Format: https://<resource>.services.ai.azure.com/api/projects/<project>/applications/<app-name>/protocols/openai")
    sys.exit(1)

# Log level configuration
# DEBUG = all events (verbose), INFO = tool calls only, WARN = errors only, OFF = no logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# =============================================================================
# INITIALIZATION
# =============================================================================

print("Initializing Foundry Application Client (Streaming)...")
print(f"Endpoint: {APP_ENDPOINT}")
print(f"Log Level: {LOG_LEVEL}")

# Create Azure AD token provider for authentication
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default"
)

# Create OpenAI client pointing to the published application
client = OpenAI(
    api_key=token_provider(),
    base_url=APP_ENDPOINT,
    default_query={"api-version": "2025-11-15-preview"}
)

print("Connected to Agent Application (Streaming Mode)")


def refresh_token():
    """Refresh the authentication token if needed."""
    global client
    client.api_key = token_provider()


def build_conversation_input(history, new_message):
    """
    Build the input for a multi-turn conversation.
    
    Published applications are stateless - we must send the full
    conversation history with each request.
    """
    messages = []
    
    for msg in history:
        messages.append({
            "type": "message",
            "role": msg["role"],
            "content": msg["content"]
        })
    
    messages.append({
        "type": "message",
        "role": "user",
        "content": new_message
    })
    
    return messages


def stream_response(input_items, log_level=None):
    """
    Send a request and stream the response token-by-token.
    
    Handles both text streaming and tool call events, displaying them
    in a clear, non-confusing format.
    
    Args:
        input_items: The conversation input items
        log_level: Override log level (DEBUG, INFO, WARN, OFF). Uses env var if None.
    
    Returns:
        tuple: (full_response_text, response_object, tool_calls)
    """
    # Use provided log_level or fall back to global LOG_LEVEL
    current_log_level = log_level or LOG_LEVEL
    
    stream = client.responses.create(
        stream=True,
        input=input_items,
    )
    
    full_text = ""
    final_response = None
    tool_calls = []  # Track all tool calls for this response
    
    # Track state for clean output formatting
    is_streaming_text = False
    pending_tool_calls = {}  # Track in-progress tool calls by ID (for MCP calls)
    pending_mcp_args = {}  # Track streaming MCP arguments by item_id
    
    # Debug: collect all unique event types seen
    seen_event_types = set()
    
    # Pydantic internal attributes to skip in debug output
    SKIP_ATTRS = {'model_computed_fields', 'model_config', 'model_extra', 
                  'model_fields', 'model_fields_set', 'model_post_init',
                  'model_construct', 'model_copy', 'model_dump', 'model_dump_json',
                  'model_json_schema', 'model_parametrized_name', 'model_rebuild',
                  'model_validate', 'model_validate_json', 'model_validate_strings'}
    
    for event in stream:
        event_type = getattr(event, 'type', None)
        
        # DEBUG level: print all events with meaningful details (skip pydantic internals)
        if current_log_level == "DEBUG" and event_type not in seen_event_types:
            seen_event_types.add(event_type)
            print(f"\n[DEBUG] Event: {event_type}")
            # Print only meaningful attributes (skip pydantic model internals)
            for attr in dir(event):
                if not attr.startswith('_') and attr not in SKIP_ATTRS:
                    try:
                        val = getattr(event, attr)
                        if not callable(val):
                            val_str = str(val)[:150] if len(str(val)) > 150 else str(val)
                            print(f"[DEBUG]   {attr}: {val_str}")
                    except:
                        pass
        
        if event_type == "response.created":
            # Response started - don't print "Assistant:" yet, wait for content
            pass
        
        # =====================================================================
        # MCP TOOL EVENTS - Azure Foundry uses MCP (Model Context Protocol)
        # Log at INFO level or higher (INFO, DEBUG)
        # =====================================================================
        
        elif event_type == "response.output_item.added":
            # A new output item is starting
            item = getattr(event, 'item', None)
            if item:
                item_type = getattr(item, 'type', None)
                item_id = getattr(item, 'id', None)
                
                # Handle MCP tool calls (Azure Foundry's way)
                if item_type == "mcp_call":
                    tool_name = getattr(item, 'name', None) or getattr(item, 'server_label', 'unknown_tool')
                    if current_log_level in ("DEBUG", "INFO"):
                        print(f"\n🔧 Calling tool: {tool_name}")
                    pending_tool_calls[item_id] = {
                        'name': tool_name,
                        'arguments': '',
                        'id': item_id
                    }
                
                # Handle MCP list tools (discovery phase)
                elif item_type == "mcp_list_tools":
                    server_label = getattr(item, 'server_label', 'unknown')
                    if current_log_level == "DEBUG":
                        print(f"\n🔍 Discovering tools from: {server_label}")
                
                # Handle standard function calls (if any)
                elif item_type == "function_call":
                    func_name = getattr(item, 'name', 'unknown_tool')
                    if current_log_level in ("DEBUG", "INFO"):
                        print(f"\n🔧 Calling tool: {func_name}")
                    pending_tool_calls[item_id] = {
                        'name': func_name,
                        'arguments': '',
                        'call_id': getattr(item, 'call_id', item_id)
                    }
        
        # MCP call starting
        elif event_type == "response.mcp_call.in_progress":
            item_id = getattr(event, 'item_id', None)
            if item_id and item_id not in pending_mcp_args:
                pending_mcp_args[item_id] = ""
        
        # MCP call arguments streaming
        elif event_type == "response.mcp_call_arguments.delta":
            item_id = getattr(event, 'item_id', None)
            delta = getattr(event, 'delta', '')
            if item_id:
                if item_id not in pending_mcp_args:
                    pending_mcp_args[item_id] = ""
                pending_mcp_args[item_id] += delta
        
        # MCP call arguments complete
        elif event_type == "response.mcp_call_arguments.done":
            item_id = getattr(event, 'item_id', None)
            arguments = getattr(event, 'arguments', '{}')
            
            # Pretty print the arguments (only at DEBUG level)
            if current_log_level == "DEBUG":
                try:
                    args_parsed = json.loads(arguments) if arguments else {}
                    args_display = json.dumps(args_parsed, indent=2)
                    # Indent each line for clean display
                    args_lines = args_display.split('\n')
                    if len(args_lines) > 10:
                        # Truncate if too long
                        args_display = '\n'.join(args_lines[:10]) + '\n   ... (truncated)'
                    args_display = '\n'.join('   ' + line for line in args_display.split('\n'))
                    print(f"   Arguments:\n{args_display}")
                except:
                    print(f"   Arguments: {arguments[:200]}..." if len(arguments) > 200 else f"   Arguments: {arguments}")
            
            # Store for tracking
            if item_id and item_id in pending_tool_calls:
                pending_tool_calls[item_id]['arguments'] = arguments
        
        # MCP call completed
        elif event_type == "response.mcp_call.completed":
            item_id = getattr(event, 'item_id', None)
            if item_id and item_id in pending_tool_calls:
                tool_info = pending_tool_calls[item_id]
                tool_calls.append({
                    'name': tool_info['name'],
                    'arguments': tool_info.get('arguments', ''),
                    'id': item_id
                })
                if current_log_level in ("DEBUG", "INFO"):
                    print(f"   ✅ Tool call completed")
                del pending_tool_calls[item_id]
            if item_id in pending_mcp_args:
                del pending_mcp_args[item_id]
        
        # MCP list tools completed
        elif event_type == "response.mcp_list_tools.completed":
            if current_log_level == "DEBUG":
                print(f"   ✅ Tool discovery completed")
        
        elif event_type == "response.output_item.done":
            # An output item is complete
            item = getattr(event, 'item', None)
            if item:
                item_type = getattr(item, 'type', None)
                item_id = getattr(item, 'id', None)
                
                # Handle MCP list tools completion with tool info
                if item_type == "mcp_list_tools":
                    tools = getattr(item, 'tools', [])
                    if tools and current_log_level == "DEBUG":
                        tool_names = [getattr(t, 'name', 'unknown') for t in tools[:5]]
                        print(f"   Available tools: {', '.join(tool_names)}")
                        if len(tools) > 5:
                            print(f"   ... and {len(tools) - 5} more")
                
                # Handle standard function_call completion
                elif item_type == "function_call":
                    func_name = getattr(item, 'name', 'unknown_tool')
                    func_args = getattr(item, 'arguments', '{}')
                    call_id = getattr(item, 'call_id', item_id)
                    
                    if current_log_level == "DEBUG":
                        try:
                            args_parsed = json.loads(func_args) if func_args else {}
                            args_display = json.dumps(args_parsed, indent=2)
                            args_display = '\n'.join('   ' + line for line in args_display.split('\n'))
                            print(f"   Arguments:\n{args_display}")
                        except:
                            print(f"   Arguments: {func_args}")
                    
                    tool_calls.append({
                        'name': func_name,
                        'arguments': func_args,
                        'call_id': call_id
                    })
                    
                    if item_id in pending_tool_calls:
                        del pending_tool_calls[item_id]
                
                elif item_type == "function_call_output":
                    # Tool result came back (only show at DEBUG level)
                    if current_log_level == "DEBUG":
                        output = getattr(item, 'output', '')
                        display_output = output[:500] + "..." if len(output) > 500 else output
                        
                        try:
                            output_parsed = json.loads(output)
                            display_output = json.dumps(output_parsed, indent=2)
                            if len(display_output) > 500:
                                display_output = display_output[:500] + "... (truncated)"
                            display_output = '\n'.join('   ' + line for line in display_output.split('\n'))
                            print(f"📤 Tool result:\n{display_output}")
                        except:
                            print(f"📤 Tool result: {display_output}")
                        print()
                
                elif item_type == "message":
                    # Check for annotations (citations)
                    content = getattr(item, 'content', [])
                    if content and len(content) > 0:
                        last_content = content[-1]
                        if getattr(last_content, 'type', None) == "output_text":
                            annotations = getattr(last_content, 'annotations', [])
                            if annotations:
                                print("\n\n📚 Citations:")
                                for ann in annotations:
                                    if getattr(ann, 'type', None) == "url_citation":
                                        print(f"   - {ann.url}")
                                    elif getattr(ann, 'type', None) == "file_citation":
                                        print(f"   - {getattr(ann, 'file_id', 'unknown')}")
        
        # =====================================================================
        # TEXT STREAMING EVENTS - The actual assistant response
        # =====================================================================
        
        elif event_type == "response.output_text.delta":
            # Streaming text delta - print immediately
            if not is_streaming_text:
                # First text chunk - print the "Assistant:" header
                print("\nAssistant: ", end="", flush=True)
                is_streaming_text = True
            
            delta = getattr(event, 'delta', '')
            print(delta, end="", flush=True)
            full_text += delta
            
        elif event_type == "response.text.done":
            # Text generation complete
            pass
            
        elif event_type == "response.completed":
            # Full response complete
            final_response = getattr(event, 'response', None)
            
        elif event_type == "error":
            # Handle errors
            error = getattr(event, 'error', None)
            print(f"\n\n❌ Stream Error: {error}")
            break
    
    print("\n")  # New line after streaming completes
    
    # Print summary if tools were called (at INFO or DEBUG level)
    if tool_calls and current_log_level in ("DEBUG", "INFO"):
        print(f"📊 Tools used in this response: {', '.join(tc['name'] for tc in tool_calls)}")
        print()
    
    return full_text, final_response, tool_calls


def main():
    """Main interactive loop with streaming responses."""
    
    # Use LOG_LEVEL from environment, can be overridden with --debug flag
    global LOG_LEVEL
    current_log_level = LOG_LEVEL
    
    # --debug flag overrides to DEBUG level
    if "--debug" in sys.argv:
        current_log_level = "DEBUG"
    
    print("\n" + "=" * 60)
    print("Foundry Agent Application - Streaming Mode")
    print("=" * 60)
    print("Responses stream token-by-token for real-time feedback.")
    if current_log_level in ("DEBUG", "INFO"):
        print("🔧 Tool calls are displayed as they happen.")
    if current_log_level == "DEBUG":
        print("🐛 DEBUG MODE - All events will be logged")
    print()
    print("Commands:")
    print("  Type your questions and press Enter")
    print("  'new'    - Start a new conversation")
    print("  'debug'  - Set log level to DEBUG")
    print("  'info'   - Set log level to INFO")
    print("  'quiet'  - Set log level to OFF (no tool logging)")
    print("  'tools'  - Show tool usage summary")
    print("  Ctrl+C   - Exit")
    print("=" * 60 + "\n")
    
    # Maintain conversation history locally
    # Published applications are stateless - no server-side history
    conversation_history = []
    total_tool_calls = []  # Track all tools used in session
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() == 'new':
                conversation_history = []
                total_tool_calls = []
                print("Started new conversation!\n")
                continue
            
            if user_input.lower() == 'debug':
                current_log_level = "DEBUG"
                print(f"\n🐛 Log level set to: DEBUG (all events)\n")
                continue
            
            if user_input.lower() == 'info':
                current_log_level = "INFO"
                print(f"\nℹ️  Log level set to: INFO (tool calls only)\n")
                continue
            
            if user_input.lower() in ('quiet', 'off'):
                current_log_level = "OFF"
                print(f"\n🔇 Log level set to: OFF (no tool logging)\n")
                continue
            
            if user_input.lower() == 'tools':
                # Show tool usage summary
                if total_tool_calls:
                    print("\n📊 Tools used in this session:")
                    tool_counts = {}
                    for tc in total_tool_calls:
                        tool_counts[tc['name']] = tool_counts.get(tc['name'], 0) + 1
                    for name, count in tool_counts.items():
                        print(f"   {name}: {count} call(s)")
                    print()
                else:
                    print("\n📊 No tools have been called yet in this session.\n")
                continue
            
            # Refresh token before making request
            refresh_token()
            
            # Build the request with full conversation history
            input_items = build_conversation_input(conversation_history, user_input)
            
            # Stream the response with current log level
            response_text, response, tool_calls = stream_response(input_items, log_level=current_log_level)
            
            # Track tools used
            total_tool_calls.extend(tool_calls)
            
            # Store in conversation history for multi-turn context
            conversation_history.append({"role": "user", "content": user_input})
            if response_text:
                conversation_history.append({"role": "assistant", "content": response_text})
            
        except KeyboardInterrupt:
            print("\n\nExiting... Goodbye!")
            if total_tool_calls:
                print(f"📊 Session summary: {len(total_tool_calls)} tool call(s) made")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            # If authentication error, try refreshing token
            if "401" in str(e) or "unauthorized" in str(e).lower():
                print("Attempting to refresh authentication...")
                refresh_token()


if __name__ == "__main__":
    main()
