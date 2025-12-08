"""
Create Agent - Programmatic Agent Creation for Azure AI Foundry
================================================================

This script demonstrates how to programmatically create an agent in Azure AI Foundry
using the Python SDK. This is useful for CI/CD pipelines, infrastructure-as-code,
or when you need to create agents dynamically.

Use Case:
---------
- Automate agent creation as part of deployment pipelines
- Create agents programmatically instead of through the portal
- Version control agent configurations alongside your code
- Create temporary or test agents for development

Key Concepts:
-------------
1. Agent Versioning: Each call to create_version() creates a new version of the agent.
   If the agent doesn't exist, it creates a new agent with version 1.

2. PromptAgentDefinition: Defines the agent's behavior including:
   - model: The deployed model to use (e.g., gpt-4o)
   - instructions: System prompt that guides the agent's behavior

3. Agent Naming Rules:
   - Must start and end with alphanumeric characters
   - Can contain hyphens (-) in the middle (NOT underscores)
   - Maximum 63 characters

Note:
-----
This creates a basic agent without tools or knowledge bases. To add MCP tools,
Azure AI Search connections, or other capabilities, configure them in the
Azure AI Foundry portal or extend this script with additional tool definitions.

Required Environment Variables:
-------------------------------
- AZURE_AI_FOUNDRY_PROJECT_ENDPOINT: The endpoint URL for your AI Foundry project
- AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME: The name of your deployed model

Authentication:
---------------
Uses DefaultAzureCredential which supports multiple authentication methods.
"""

import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

# Load environment variables from .env file
load_dotenv()

# Initialize the AI Project Client with Azure credentials
project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# Create a new version of the agent
# If the agent doesn't exist, this creates it with version 1
agent = project_client.agents.create_version(
    agent_name="dummy-agent",  # Note: Use hyphens, not underscores
    definition=PromptAgentDefinition(
        model=os.environ["AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT_NAME"],
        instructions="You are a helpful assistant that answers general questions",
    ),
)

print(f"Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")