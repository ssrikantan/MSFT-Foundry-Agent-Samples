"""
Foundry Agent Web App - Backend Server
=======================================

FastAPI server that connects to the Azure Foundry published agent
and streams responses via Server-Sent Events (SSE).

Features:
    - SSE streaming for real-time token delivery
    - Tool/MCP event forwarding for UI display
    - Azure AD authentication
    - CORS support for local development

Usage:
    cd webapp
    uvicorn server:app --reload --port 8000

Then open: http://localhost:8000
"""

import os
import sys
import json
import asyncio
import queue
import threading
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Load environment variables from project root
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

# =============================================================================
# CONFIGURATION
# =============================================================================

APP_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_APP_ENDPOINT")

if not APP_ENDPOINT:
    print("Error: AZURE_AI_FOUNDRY_APP_ENDPOINT not set in environment")
    print("Set this in your .env file at the project root.")
    sys.exit(1)

# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="Foundry Agent Chat",
    description="Web chat interface for Azure AI Foundry Published Agent"
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# =============================================================================
# AZURE CLIENT
# =============================================================================

def get_openai_client() -> OpenAI:
    """Create authenticated OpenAI client for Foundry endpoint."""
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://ai.azure.com/.default"
    )
    
    return OpenAI(
        api_key=token_provider(),
        base_url=APP_ENDPOINT,
        default_query={"api-version": "2025-11-15-preview"}
    )

# =============================================================================
# MODELS
# =============================================================================

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

# =============================================================================
# SSE STREAMING
# =============================================================================

async def stream_agent_response(messages: list[dict]) -> AsyncGenerator[str, None]:
    """
    Stream the agent response as Server-Sent Events.
    
    Event types sent to frontend:
        - text_delta: Streaming text content
        - tool_start: Tool call started (name, id)
        - tool_args: Tool arguments (for expandable display)
        - tool_done: Tool call completed
        - tool_discovery: Tool discovery phase
        - done: Stream complete
        - error: Error occurred
    """
    try:
        client = get_openai_client()
        
        # Build input items from messages
        input_items = [
            {"type": "message", "role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]
        
        # Run the synchronous OpenAI stream in a thread to avoid blocking
        # This allows SSE events to flush immediately
        event_queue = queue.Queue()
        stream_done = False
        
        def stream_to_queue():
            nonlocal stream_done
            try:
                stream = client.responses.create(
                    stream=True,
                    input=input_items,
                )
                for event in stream:
                    event_queue.put(event)
                event_queue.put(None)  # Signal completion
            except Exception as e:
                event_queue.put(e)
            finally:
                stream_done = True
        
        # Start streaming in background thread
        stream_thread = threading.Thread(target=stream_to_queue, daemon=True)
        stream_thread.start()
        
        pending_tools = {}  # Track tool calls by ID
        pending_args = {}   # Track streaming arguments
        
        # Process events from queue with async yielding
        while True:
            try:
                # Non-blocking get with small timeout
                event = event_queue.get(timeout=0.05)
                
                if event is None:
                    break  # Stream complete
                
                if isinstance(event, Exception):
                    raise event
                    
                event_type = getattr(event, 'type', None)
                
                # Text streaming
                if event_type == "response.output_text.delta":
                    delta = getattr(event, 'delta', '')
                    yield f"data: {json.dumps({'type': 'text_delta', 'content': delta})}\n\n"
                    await asyncio.sleep(0)  # Force flush
                
                # New output item added
                elif event_type == "response.output_item.added":
                    item = getattr(event, 'item', None)
                    if item:
                        item_type = getattr(item, 'type', None)
                        item_id = getattr(item, 'id', None)
                        
                        # MCP tool call starting
                        if item_type == "mcp_call":
                            tool_name = getattr(item, 'name', None) or getattr(item, 'server_label', 'Tool')
                            pending_tools[item_id] = {'name': tool_name, 'arguments': ''}
                            yield f"data: {json.dumps({'type': 'tool_start', 'id': item_id, 'name': tool_name})}\n\n"
                            await asyncio.sleep(0)  # Force flush
                        
                        # Tool discovery
                        elif item_type == "mcp_list_tools":
                            server_label = getattr(item, 'server_label', 'knowledge base')
                            yield f"data: {json.dumps({'type': 'tool_discovery', 'source': server_label})}\n\n"
                            await asyncio.sleep(0)  # Force flush
                        
                        # Standard function call
                        elif item_type == "function_call":
                            func_name = getattr(item, 'name', 'Tool')
                            pending_tools[item_id] = {'name': func_name, 'arguments': ''}
                            yield f"data: {json.dumps({'type': 'tool_start', 'id': item_id, 'name': func_name})}\n\n"
                            await asyncio.sleep(0)  # Force flush
                
                # MCP call in progress
                elif event_type == "response.mcp_call.in_progress":
                    item_id = getattr(event, 'item_id', None)
                    if item_id and item_id not in pending_args:
                        pending_args[item_id] = ""
                
                # MCP arguments streaming
                elif event_type == "response.mcp_call_arguments.delta":
                    item_id = getattr(event, 'item_id', None)
                    delta = getattr(event, 'delta', '')
                    if item_id:
                        if item_id not in pending_args:
                            pending_args[item_id] = ""
                        pending_args[item_id] += delta
                
                # MCP arguments complete
                elif event_type == "response.mcp_call_arguments.done":
                    item_id = getattr(event, 'item_id', None)
                    arguments = getattr(event, 'arguments', '{}')
                    
                    if item_id and item_id in pending_tools:
                        pending_tools[item_id]['arguments'] = arguments
                        # Send arguments for expandable display
                        try:
                            args_parsed = json.loads(arguments) if arguments else {}
                            yield f"data: {json.dumps({'type': 'tool_args', 'id': item_id, 'arguments': args_parsed})}\n\n"
                        except:
                            yield f"data: {json.dumps({'type': 'tool_args', 'id': item_id, 'arguments': arguments})}\n\n"
                        await asyncio.sleep(0)  # Force flush
                
                # MCP call completed
                elif event_type == "response.mcp_call.completed":
                    item_id = getattr(event, 'item_id', None)
                    if item_id:
                        tool_info = pending_tools.get(item_id, {})
                        yield f"data: {json.dumps({'type': 'tool_done', 'id': item_id, 'name': tool_info.get('name', 'Tool')})}\n\n"
                        await asyncio.sleep(0)  # Force flush
                        pending_tools.pop(item_id, None)
                        pending_args.pop(item_id, None)
                
                # Tool discovery completed
                elif event_type == "response.mcp_list_tools.completed":
                    yield f"data: {json.dumps({'type': 'tool_discovery_done'})}\n\n"
                    await asyncio.sleep(0)  # Force flush
                
                # Output item done - check for function_call completion
                elif event_type == "response.output_item.done":
                    item = getattr(event, 'item', None)
                    if item:
                        item_type = getattr(item, 'type', None)
                        item_id = getattr(item, 'id', None)
                        
                        if item_type == "function_call":
                            func_args = getattr(item, 'arguments', '{}')
                            try:
                                args_parsed = json.loads(func_args) if func_args else {}
                                yield f"data: {json.dumps({'type': 'tool_args', 'id': item_id, 'arguments': args_parsed})}\n\n"
                            except:
                                pass
                            yield f"data: {json.dumps({'type': 'tool_done', 'id': item_id})}\n\n"
                            await asyncio.sleep(0)  # Force flush
                            pending_tools.pop(item_id, None)
                        
                        # Check for citations
                        elif item_type == "message":
                            content = getattr(item, 'content', [])
                            if content and len(content) > 0:
                                last_content = content[-1]
                                if getattr(last_content, 'type', None) == "output_text":
                                    annotations = getattr(last_content, 'annotations', [])
                                    citations = []
                                    for ann in annotations:
                                        if getattr(ann, 'type', None) == "url_citation":
                                            citations.append({'type': 'url', 'url': ann.url})
                                        elif getattr(ann, 'type', None) == "file_citation":
                                            citations.append({'type': 'file', 'file_id': getattr(ann, 'file_id', 'unknown')})
                                    if citations:
                                        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
                                        await asyncio.sleep(0)  # Force flush
                
                # Stream complete
                elif event_type == "response.completed":
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                
                # Error
                elif event_type == "error":
                    error = getattr(event, 'error', 'Unknown error')
                    yield f"data: {json.dumps({'type': 'error', 'error': str(error)})}\n\n"
                    
            except queue.Empty:
                # No event yet, yield control to event loop
                await asyncio.sleep(0.01)
                continue
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

# =============================================================================
# ROUTES
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main chat interface."""
    index_path = static_path / "index.html"
    return HTMLResponse(content=index_path.read_text(), status_code=200)


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Stream chat response via Server-Sent Events.
    
    The frontend sends the full conversation history,
    and we stream back events for text, tool calls, etc.
    """
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    return StreamingResponse(
        stream_agent_response(messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "endpoint_configured": bool(APP_ENDPOINT)}


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("Foundry Agent Web App")
    print("=" * 60)
    print(f"Endpoint: {APP_ENDPOINT}")
    print("\nStarting server at http://localhost:8000")
    print("=" * 60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
