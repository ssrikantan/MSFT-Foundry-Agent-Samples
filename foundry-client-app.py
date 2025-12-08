"""
Foundry Client App - Direct Model Interaction (Interactive Mode)
=================================================================

This script demonstrates how to use the Azure AI Foundry Responses API to interact
directly with a deployed model (e.g., GPT-4, GPT-4o) without using a pre-configured agent.

Use Case:
---------
- Simple, direct LLM interactions without agent orchestration
- Quick prototyping and testing of model responses
- Scenarios where you don't need tools, knowledge bases, or MCP integrations
- Interactive chat sessions with continuous user input
- Multi-turn conversations with context preservation via server-side conversation

Key Concepts:
-------------
- Uses the OpenAI-compatible client obtained from AIProjectClient
- Calls the Responses API directly with a model deployment name
- No agent configuration, tools, or MCP approval handling required
- Clients are initialized once and reused for all requests (optimized for performance)
- Conversation context is maintained server-side using the conversations API

Required Environment Variables:
-------------------------------
- AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: The endpoint URL for your AI Foundry project
- AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME: The name of your deployed model

Authentication:
---------------
Uses DefaultAzureCredential which supports multiple authentication methods:
- Azure CLI credentials (az login)
- Managed Identity
- Environment variables
- Visual Studio Code credentials

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
print(f"Model: {os.environ['AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME']}")

# Initialize the AI Project Client with Azure credentials (one-time setup)
# This connection is reused for all subsequent requests
project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# Get the OpenAI-compatible client (one-time setup)
# This client maintains connection pooling for optimal performance
openai_client = project_client.get_openai_client()

# Cache the model name to avoid repeated environment lookups
model_name = os.environ["AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME"]


# =============================================================================
# INTERACTIVE CHAT LOOP
# =============================================================================

def create_conversation():
    """Create a new conversation and return its ID."""
    conversation = openai_client.conversations.create()
    print(f"Created conversation (id: {conversation.id})")
    return conversation.id


def main():
    """Main interactive loop for chatting with the model."""
    
    # Create a conversation for multi-turn interactions
    # The conversation ID maintains all context server-side
    conversation_id = create_conversation()
    
    print("\n" + "=" * 60)
    print("Azure AI Foundry Client - Interactive Mode")
    print("=" * 60)
    print("Type your questions and press Enter to get responses.")
    print("Type 'new' to start a new conversation.")
    print("Press Ctrl+C to exit.\n")
    
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            # Skip empty inputs
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() == 'new':
                conversation_id = create_conversation()
                print("Started new conversation!\n")
                continue
            
            # Make a call to the model with the conversation ID
            # The conversation maintains all context server-side
            response = openai_client.responses.create(
                model=model_name,
                conversation=conversation_id,
                input=user_input,
            )
            
            print(f"\nAssistant: {response.output_text}\n")
            
        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\n\nExiting... Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()