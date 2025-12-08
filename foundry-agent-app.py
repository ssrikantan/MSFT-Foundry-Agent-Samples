"""
Foundry Agent App - Agent-Based Interaction with MCP Support (Interactive Mode)
================================================================================

This script demonstrates how to interact with a pre-configured agent in Azure AI Foundry
that uses MCP (Model Context Protocol) to access external tools and knowledge bases.

Use Case:
---------
- Chat with agents configured in the Azure AI Foundry portal
- Access knowledge bases (e.g., Azure AI Search, Bing grounding) through MCP
- Multi-turn conversations with context preservation via server-side conversation
- Automatic approval of MCP tool calls for seamless agent execution
- Interactive chat sessions with continuous user input

Key Concepts:
-------------
1. Agent Reference: Instead of specifying a model, we reference a named agent
   configured in AI Foundry using extra_body={"agent": {"name": ..., "type": "agent_reference"}}

2. MCP (Model Context Protocol): A protocol that allows agents to call external tools
   and knowledge bases. When an agent needs to use MCP tools, it returns an
   "mcp_approval_request" that must be approved before execution continues.

3. Conversations: Used for multi-turn interactions. The conversation ID maintains
   all context server-side across multiple exchanges.

4. Response Chaining: For follow-up questions, use previous_response_id to maintain
   both conversation context and MCP approval chains.

MCP Approval Flow:
------------------
1. Agent sends a response with status="incomplete" and mcp_approval_request items
2. Client approves/rejects each request by sending mcp_approval_response
3. Agent continues execution with approved tool calls
4. This repeats until the response is complete

Performance Optimizations:
--------------------------
- Clients are initialized once at startup and reused for all requests
- Conversation is created once and maintained throughout the session
- Agent name is cached to avoid repeated environment lookups

Required Environment Variables:
-------------------------------
- AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: The endpoint URL for your AI Foundry project
- AZURE_AI_FOUNDRY_AGENT_NAME: The name of the agent configured in AI Foundry

Authentication:
---------------
Uses DefaultAzureCredential which supports multiple authentication methods.

Usage:
------
Run the script and type your questions. Press Ctrl+C to exit.
Type 'new' to start a new conversation.
"""

import os
import sys
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# INITIALIZATION (Done once at startup for optimal performance)
# =============================================================================

print("Initializing Azure AI Foundry connection...")
print(f"Endpoint: {os.environ['AZURE_AI_FOUNDRY_PROJECT_ENDPOINT']}")

# Initialize the AI Project Client with Azure credentials (one-time setup)
# This connection is reused for all subsequent requests
project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# Get the agent name from environment and cache it
agent_name = os.environ["AZURE_AI_FOUNDRY_AGENT_NAME"]
print(f"Agent: {agent_name}")

# Get the OpenAI-compatible client (one-time setup)
# This client maintains connection pooling for optimal performance
openai_client = project_client.get_openai_client()


def process_response_with_mcp_approval(response):
    """
    Process a response and automatically approve any pending MCP tool calls.
    
    When an agent uses MCP-enabled tools (like knowledge bases or external APIs),
    the response may contain approval requests that must be handled before the
    agent can continue execution.
    
    Args:
        response: The response object from openai_client.responses.create()
    
    Returns:
        The final response after all MCP approvals have been processed.
    
    MCP Approval Items:
        - mcp_approval_request: Sent by agent when it needs to call an MCP tool
        - mcp_approval_response: Sent by client to approve/reject the request
    
    Note:
        This implementation auto-approves all MCP requests. In production,
        you may want to add validation or user confirmation for sensitive operations.
    """
    # Check if there are pending MCP approval requests
    while response.status == "incomplete" or (hasattr(response, 'output') and any(
        item.type == "mcp_approval_request" for item in response.output if hasattr(item, 'type')
    )):
        # Find MCP approval requests in the output
        approval_requests = [
            item for item in response.output 
            if hasattr(item, 'type') and item.type == "mcp_approval_request"
        ]
        
        if not approval_requests:
            break
            
        # Approve all pending MCP requests
        approvals = []
        for req in approval_requests:
            print(f"Approving MCP request: {req.id}")
            approvals.append({
                "type": "mcp_approval_response",
                "approve": True,
                "approval_request_id": req.id
            })
        
        # Continue the response with approvals
        # Note: Use previous_response_id WITHOUT conversation parameter
        # to maintain the approval chain correctly
        response = openai_client.responses.create(
            extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
            input=approvals,
            previous_response_id=response.id
        )
    
    return response


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def create_conversation():
    """Create a new conversation and return the conversation object."""
    conversation = openai_client.conversations.create()
    print(f"Created conversation (id: {conversation.id})")
    return conversation


def main():
    """Main interactive loop for chatting with the agent."""
    
    # Create a conversation for multi-turn interactions
    # The conversation ID maintains all context server-side
    conversation = create_conversation()
    
    print("\n" + "=" * 60)
    print("Azure AI Foundry Agent - Interactive Mode")
    print("=" * 60)
    print(f"Connected to agent: {agent_name}")
    print("Type your questions and press Enter to get responses.")
    print("The agent has access to knowledge bases via MCP.")
    print("Type 'new' to start a new conversation.")
    print("Press Ctrl+C to exit.\n")
    
    # Track the last response for chaining follow-up questions (MCP approval chain)
    last_response = None
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Skip empty inputs
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() == 'new':
                conversation = create_conversation()
                last_response = None
                print("Started new conversation!\n")
                continue
            
            # Send message to the agent
            # - For the first message, use conversation.id
            # - For follow-ups, use previous_response_id to maintain MCP approval chain
            if last_response is None:
                # First message in the conversation
                response = openai_client.responses.create(
                    conversation=conversation.id,
                    extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
                    input=user_input,
                )
            else:
                # Follow-up message - use previous_response_id for context + approvals
                response = openai_client.responses.create(
                    previous_response_id=last_response.id,
                    extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
                    input=user_input,
                )
            
            # Process any MCP approval requests (agent may need to query knowledge base)
            response = process_response_with_mcp_approval(response)
            
            # Store the response for chaining the next message
            last_response = response
            
            print(f"\nAssistant: {response.output_text}\n")
            
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\n\nExiting... Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()