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

# =============================================================================
# INITIALIZATION
# =============================================================================

print("Initializing Foundry Application Client (Streaming)...")
print(f"Endpoint: {APP_ENDPOINT}")

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


def stream_response(input_items):
    """
    Send a request and stream the response token-by-token.
    
    Args:
        input_items: The conversation input items
    
    Returns:
        tuple: (full_response_text, response_object)
    """
    stream = client.responses.create(
        stream=True,
        input=input_items,
    )
    
    full_text = ""
    final_response = None
    
    print("\nAssistant: ", end="", flush=True)
    
    for event in stream:
        event_type = getattr(event, 'type', None)
        
        if event_type == "response.created":
            # Response started
            pass
            
        elif event_type == "response.output_text.delta":
            # Streaming text delta - print immediately
            delta = getattr(event, 'delta', '')
            print(delta, end="", flush=True)
            full_text += delta
            
        elif event_type == "response.text.done":
            # Text generation complete
            pass
            
        elif event_type == "response.output_item.done":
            # An output item is complete
            item = getattr(event, 'item', None)
            if item and getattr(item, 'type', None) == "message":
                # Check for annotations (citations)
                content = getattr(item, 'content', [])
                if content and len(content) > 0:
                    last_content = content[-1]
                    if getattr(last_content, 'type', None) == "output_text":
                        annotations = getattr(last_content, 'annotations', [])
                        if annotations:
                            print("\n\nCitations:")
                            for ann in annotations:
                                if getattr(ann, 'type', None) == "url_citation":
                                    print(f"  - {ann.url}")
                                elif getattr(ann, 'type', None) == "file_citation":
                                    print(f"  - {getattr(ann, 'file_id', 'unknown')}")
            
        elif event_type == "response.completed":
            # Full response complete
            final_response = getattr(event, 'response', None)
            
        elif event_type == "error":
            # Handle errors
            error = getattr(event, 'error', None)
            print(f"\n\nStream Error: {error}")
            break
    
    print("\n")  # New line after streaming completes
    
    return full_text, final_response


def main():
    """Main interactive loop with streaming responses."""
    
    print("\n" + "=" * 60)
    print("Foundry Agent Application - Streaming Mode")
    print("=" * 60)
    print("Responses stream token-by-token for real-time feedback.")
    print("Type your questions and press Enter to get responses.")
    print("Type 'new' to start a new conversation.")
    print("Press Ctrl+C to exit.\n")
    
    # Maintain conversation history locally
    # Published applications are stateless - no server-side history
    conversation_history = []
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() == 'new':
                conversation_history = []
                print("Started new conversation!\n")
                continue
            
            # Refresh token before making request
            refresh_token()
            
            # Build the request with full conversation history
            input_items = build_conversation_input(conversation_history, user_input)
            
            # Stream the response
            response_text, response = stream_response(input_items)
            
            # Store in conversation history for multi-turn context
            conversation_history.append({"role": "user", "content": user_input})
            if response_text:
                conversation_history.append({"role": "assistant", "content": response_text})
            
        except KeyboardInterrupt:
            print("\n\nExiting... Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}\n")
            # If authentication error, try refreshing token
            if "401" in str(e) or "unauthorized" in str(e).lower():
                print("Attempting to refresh authentication...")
                refresh_token()


if __name__ == "__main__":
    main()
