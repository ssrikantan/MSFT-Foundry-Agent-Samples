"""
Foundry Application Client - Call Published Agent Applications
===============================================================

This script demonstrates how to call a published Agent Application in Azure AI Foundry
using the OpenAI-compatible Responses API protocol.

Use Case:
---------
- Call agents that have been published as Agent Applications
- Share agents with external users without giving them project access
- Access agents via a stable endpoint that persists across version updates

Key Differences from Project-Based Access (foundry-agent-app.py):
------------------------------------------------------------------
1. Uses OpenAI SDK directly (not Azure AI Projects SDK)
2. Connects to the Application endpoint, not the Project endpoint
3. Client must manage conversation history (server doesn't store it)
4. Only POST /responses is available (no /conversations, /files, etc.)
5. Requires Azure AI User role on the Agent Application resource

Authentication:
---------------
Uses Azure DefaultAzureCredential with get_bearer_token_provider.
The caller must have the Azure AI User role on the Agent Application resource.

Multi-Turn Conversations:
-------------------------
Since the application doesn't store conversation history, we must:
1. Maintain conversation history locally
2. Send the full history with each request using the 'input' parameter

Required Environment Variables:
-------------------------------
- AZURE_AI_FOUNDRY_APP_ENDPOINT: The published application endpoint URL
  Format: https://<resource>.services.ai.azure.com/api/projects/<project>/applications/<app-name>/protocols/openai

Usage:
------
Run the script and type your questions. Press Ctrl+C to exit.
Type 'new' to start a new conversation.
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

# The published application endpoint
# Format: https://<resource>.services.ai.azure.com/api/projects/<project>/applications/<app-name>/protocols/openai
APP_ENDPOINT = os.environ.get(
    "AZURE_AI_FOUNDRY_APP_ENDPOINT",
    "https://sansri-aihub-foundryiq-resource.services.ai.azure.com/api/projects/sansri-aihub-foundryiq/applications/FoundryIQ-Contoso-Agent/protocols/openai"
)

print("Initializing Foundry Application Client...")
print(f"Endpoint: {APP_ENDPOINT}")

# =============================================================================
# AUTHENTICATION
# =============================================================================

# Create a token provider for Azure AI authentication
# Requires Azure AI User role on the Agent Application resource
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default"
)

# Initialize OpenAI client with Azure credentials
# Note: api_key is set to the token provider (callable that returns token)
client = OpenAI(
    api_key=token_provider(),  # Get initial token
    base_url=APP_ENDPOINT,
    default_query={"api-version": "2025-11-15-preview"}
)

print("Connected to Agent Application")


def refresh_token():
    """Refresh the authentication token if needed."""
    global client
    client.api_key = token_provider()


def process_response_with_mcp_approval(response):
    """
    Process a response and check for MCP approval requests.
    
    IMPORTANT: Published Agent Applications are stateless and do NOT support
    previous_response_id. This means MCP approval flows cannot be completed
    through the published endpoint.
    
    If your agent requires MCP approvals, you have two options:
    1. Reconfigure the agent's MCP tools with require_approval="never" before publishing
    2. Use the unpublished agent via foundry-agent-app.py which supports approvals
    
    Args:
        response: The response object from client.responses.create()
    
    Returns:
        The response (may be incomplete if MCP approval is required)
    """
    if hasattr(response, 'output'):
        approval_requests = [
            item for item in response.output 
            if hasattr(item, 'type') and item.type == "mcp_approval_request"
        ]
        
        if approval_requests:
            print("\n⚠️  MCP Approval Required but NOT SUPPORTED for Published Apps!")
            print("   Published Agent Applications are stateless and cannot process")
            print("   MCP approval flows (previous_response_id not supported).")
            print("\n   To fix this:")
            print("   1. Reconfigure your agent's MCP tools with require_approval='never'")
            print("   2. Or use foundry-agent-app.py for the unpublished agent\n")
            for req in approval_requests:
                print(f"   Pending approval: {req.id}")
    
    return response


def build_conversation_input(history, new_message):
    """
    Build the input for a multi-turn conversation.
    
    Since the application doesn't store conversation history server-side,
    we need to send the full conversation history with each request.
    
    Args:
        history: List of previous messages in the conversation
        new_message: The new user message to add
    
    Returns:
        List of message items for the input parameter
    """
    messages = []
    
    # Add previous conversation history
    for msg in history:
        messages.append({
            "type": "message",
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add the new user message
    messages.append({
        "type": "message",
        "role": "user",
        "content": new_message
    })
    
    return messages


def main():
    """Main interactive loop for chatting with the published agent."""
    
    print("\n" + "=" * 60)
    print("Foundry Agent Application - Interactive Mode")
    print("=" * 60)
    print("This client connects to a published Agent Application.")
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
                last_response = None
                print("Started new conversation!\n")
                continue
            
            # Refresh token before making request (tokens can expire)
            refresh_token()
            
            # Build the request with full conversation history
            # Published applications are stateless - each request is independent
            input_items = build_conversation_input(conversation_history, user_input)
            
            response = client.responses.create(
                input=input_items,
            )
            
            # Check for MCP approval requests (not supported in published apps)
            response = process_response_with_mcp_approval(response)
            
            # Store in conversation history for multi-turn context
            conversation_history.append({"role": "user", "content": user_input})
            if response.output_text:
                conversation_history.append({"role": "assistant", "content": response.output_text})
            
            # Print the response
            if response.output_text:
                print(f"\nAssistant: {response.output_text}\n")
            else:
                print("\nAssistant: (No response - may require MCP approval)\n")
            
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
