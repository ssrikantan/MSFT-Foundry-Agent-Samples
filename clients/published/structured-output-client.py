"""
Structured Output Agent Client - Test Published Agent with JSON Schema
======================================================================

This script tests a published Agent Application that uses structured JSON output.
The agent is configured to always respond with:
{
    "question": "<user's original question>",
    "response": "<assistant's answer>"
}

Purpose:
--------
Verify that structured output configured at agent creation time works
when calling the agent via its published endpoint.

Required Environment Variables:
-------------------------------
- AZURE_AI_FOUNDRY_STRUCTURED_OUTPUT_APP_ENDPOINT: The published application endpoint

Usage:
------
    python clients/published/structured-output-client.py
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Load environment variables from project root
project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(project_root / ".env")

# =============================================================================
# CONFIGURATION
# =============================================================================

APP_ENDPOINT = os.environ.get("AZURE_AI_FOUNDRY_STRUCTURED_OUTPUT_APP_ENDPOINT")

if not APP_ENDPOINT:
    print("Error: AZURE_AI_FOUNDRY_STRUCTURED_OUTPUT_APP_ENDPOINT not set in .env")
    sys.exit(1)

print("=" * 70)
print("Structured Output Agent - Client Test")
print("=" * 70)
print(f"Endpoint: {APP_ENDPOINT}")
print()

# =============================================================================
# AUTHENTICATION
# =============================================================================

print("Authenticating...")
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://ai.azure.com/.default"
)

client = OpenAI(
    api_key=token_provider(),
    base_url=APP_ENDPOINT,
    default_query={"api-version": "2025-11-15-preview"}
)
print("✅ Connected to Agent Application\n")


def refresh_token():
    """Refresh the authentication token."""
    global client
    client.api_key = token_provider()


def test_structured_output(question: str) -> dict:
    """
    Send a question to the structured output agent and verify the response format.
    
    Args:
        question: The question to ask the agent
        
    Returns:
        The parsed JSON response, or None if parsing failed
    """
    print(f"📤 Sending: {question}")
    print("-" * 50)
    
    refresh_token()
    
    response = client.responses.create(
        input=[{
            "type": "message",
            "role": "user",
            "content": question
        }]
    )
    
    raw_output = response.output_text
    print(f"📥 Raw response:\n{raw_output}")
    print("-" * 50)
    
    # Try to parse as JSON
    try:
        parsed = json.loads(raw_output)
        
        # Validate structure
        if "question" in parsed and "response" in parsed:
            print("✅ Valid structured output!")
            print(f"   question: {parsed['question'][:50]}..." if len(parsed.get('question', '')) > 50 else f"   question: {parsed.get('question')}")
            print(f"   response: {parsed['response'][:100]}..." if len(parsed.get('response', '')) > 100 else f"   response: {parsed.get('response')}")
            return parsed
        else:
            print("⚠️  JSON parsed but missing expected fields!")
            print(f"   Expected: 'question' and 'response'")
            print(f"   Got: {list(parsed.keys())}")
            return parsed
            
    except json.JSONDecodeError as e:
        print(f"❌ Response is NOT valid JSON!")
        print(f"   Error: {e}")
        return None


def run_tests():
    """Run a series of tests to verify structured output."""
    
    test_questions = [
        "What is the capital of France?",
        "Explain quantum computing in one sentence.",
        "What is 25 * 4?",
    ]
    
    print("=" * 70)
    print("RUNNING STRUCTURED OUTPUT TESTS")
    print("=" * 70)
    print()
    print("Expected response format:")
    print('  {')
    print('    "question": "<original question>",')
    print('    "response": "<assistant answer>"')
    print('  }')
    print()
    print("=" * 70)
    
    results = {"passed": 0, "failed": 0}
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n📋 TEST {i}/{len(test_questions)}")
        print("=" * 50)
        
        try:
            result = test_structured_output(question)
            
            if result and "question" in result and "response" in result:
                results["passed"] += 1
                print("✅ TEST PASSED\n")
            else:
                results["failed"] += 1
                print("❌ TEST FAILED\n")
                
        except Exception as e:
            results["failed"] += 1
            print(f"❌ TEST FAILED - Error: {e}\n")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"✅ Passed: {results['passed']}/{len(test_questions)}")
    print(f"❌ Failed: {results['failed']}/{len(test_questions)}")
    
    if results["failed"] == 0:
        print("\n🎉 All tests passed! Structured output is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    print("=" * 70)


def interactive_mode():
    """Interactive mode for testing custom questions."""
    
    print("\n" + "=" * 70)
    print("INTERACTIVE MODE")
    print("=" * 70)
    print("Type your questions to test structured output.")
    print("Type 'quit' to exit.")
    print("=" * 70 + "\n")
    
    while True:
        try:
            question = input("❓ Your question: ").strip()
            
            if not question:
                continue
                
            if question.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye!")
                break
                
            print()
            test_structured_output(question)
            print()
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        run_tests()
        
        print("\nTip: Run with --interactive for custom questions:")
        print("  python clients/published/structured-output-client.py --interactive")


if __name__ == "__main__":
    main()
