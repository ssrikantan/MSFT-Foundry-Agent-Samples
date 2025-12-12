"""
Create Structured Output Agent - Azure AI Foundry
==================================================

This script creates a simple agent that responds with structured JSON output.
No tools or knowledge base - just testing structured output capability.

The agent will always respond with a JSON object containing:
- question: The user's original question
- response: The LLM's answer

Usage:
    python ops/create-structured-output-agent.py

Required Environment Variables:
    - AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: Project endpoint URL
    - AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME: Model to use (e.g., gpt-4.1-mini)

Prerequisites:
    - Azure CLI authenticated (az login)
    - Contributor role on the AI Foundry project
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    PromptAgentDefinitionText,
    ResponseTextFormatConfigurationJsonSchema,
)

# Load environment variables from project root
project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT")
MODEL_NAME = os.environ.get("AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")

AGENT_NAME = "structured-output-test-agent"
AGENT_DESCRIPTION = "A test agent that responds with structured JSON output containing the question and response."

# Instructions that tell the agent to respond in the structured format
INSTRUCTIONS = """You are a helpful assistant that responds to user questions.

IMPORTANT: Your response will be automatically formatted as JSON with this structure:
{
  "question": "<the user's original question>",
  "response": "<your helpful answer>"
}

Always provide clear, concise, and helpful answers. The JSON formatting is handled automatically - just focus on providing a great response to the user's question."""

# JSON Schema for structured output
# This ensures the agent ALWAYS responds with this exact structure
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "question": {
            "type": "string",
            "description": "The user's original question, repeated verbatim"
        },
        "response": {
            "type": "string",
            "description": "The assistant's helpful response to the question"
        }
    },
    "required": ["question", "response"],
    "additionalProperties": False
}

# =============================================================================
# VALIDATION
# =============================================================================

if not PROJECT_ENDPOINT:
    print("Error: AZURE_AI_FOUNDRY_PROJECT_ENDPOINT not set in environment")
    sys.exit(1)

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("Azure AI Foundry - Create Structured Output Agent")
    print("=" * 70)
    print(f"Project Endpoint: {PROJECT_ENDPOINT}")
    print(f"Model: {MODEL_NAME}")
    print(f"Agent Name: {AGENT_NAME}")
    print()

    # Connect to Azure AI Foundry
    print("Connecting to Azure AI Foundry...")
    credential = DefaultAzureCredential()
    project_client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=credential,
    )
    print("✅ Connected!\n")

    # Check if agent already exists
    print("Checking for existing agents...")
    existing_agents = list(project_client.agents.list())
    existing_names = [a.name for a in existing_agents]
    
    if AGENT_NAME in existing_names:
        print(f"⚠️  Agent '{AGENT_NAME}' already exists.")
        response = input("Do you want to create a new version? (y/n): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)
    
    print()

    # Create the structured output configuration
    print("Configuring structured JSON output...")
    print(f"Schema: {RESPONSE_SCHEMA}")
    print()

    # Build the text format configuration with JSON schema
    text_format = ResponseTextFormatConfigurationJsonSchema(
        name="question_response_format",
        description="A structured response containing the original question and the assistant's answer",
        strict=True,
        schema=RESPONSE_SCHEMA  # Just pass the dict directly
    )

    text_config = PromptAgentDefinitionText(format=text_format)

    # Create the agent definition
    agent_definition = PromptAgentDefinition(
        model=MODEL_NAME,
        instructions=INSTRUCTIONS,
        text=text_config,
        # No tools - this is a simple structured output test
    )

    # Create the agent
    print(f"Creating agent '{AGENT_NAME}'...")
    try:
        agent = project_client.agents.create(
            name=AGENT_NAME,
            description=AGENT_DESCRIPTION,
            definition=agent_definition,
        )
        
        print("\n" + "=" * 70)
        print("✅ AGENT CREATED SUCCESSFULLY!")
        print("=" * 70)
        print(f"Agent Name: {agent.name}")
        print(f"Agent ID: {agent.id}")
        print(f"Model: {MODEL_NAME}")
        print(f"Structured Output: Enabled (JSON Schema)")
        print()
        print("Response Schema:")
        print("  {")
        print('    "question": "<user\'s question>",')
        print('    "response": "<assistant\'s answer>"')
        print("  }")
        print()
        print("Next Steps:")
        print("  1. Publish the agent in Azure AI Foundry portal")
        print("  2. Test with the client app or directly via API")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error creating agent: {e}")
        
        # Provide helpful error messages
        if "already exists" in str(e).lower():
            print("\nThe agent name already exists. Try a different name.")
        elif "not found" in str(e).lower():
            print("\nThe model deployment might not exist. Check MODEL_NAME.")
        elif "unauthorized" in str(e).lower() or "401" in str(e):
            print("\nAuthentication failed. Try running 'az login' again.")
        else:
            print("\nCheck your configuration and try again.")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
