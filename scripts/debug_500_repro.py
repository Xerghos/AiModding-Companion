
import sys
import os
import json
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.getcwd())

# Mock UnifiedLogger before importing ai_core
sys.modules["features.UnifiedLogger"] = MagicMock()
from features.UnifiedLogger import UnifiedLogger
def mock_write(source, level, message, details=None):
    print(f"[{source}] {level}: {message}")
    if details:
        print(f"Details: {details}")

UnifiedLogger.write = mock_write

try:
    from ai_core.code_assist_client import CodeAssistClient
    from ai_core.code_assist_converter import to_generate_content_request
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_payload(name, payload, stream=True, model="gemini-3-flash-preview"):
    print(f"\n--- Testing {name} (Stream={stream}, Model={model}) ---")
    client = CodeAssistClient()
    method = "streamGenerateContent" if stream else "generateContent"
    
    # Manually constructing the request to bypass converter for testing specific cases
    # We use client._request_streaming_post directly
    
    ca_request = {
        "model": model,
        "request": payload
    }
    
    # print(f"Sending payload: {json.dumps(payload, indent=2)}")
    
    try:
        if stream:
            chunks = list(client._request_streaming_post(method, ca_request))
            print("SUCCESS: Received chunks")
            # print(chunks)
        else:
            response = client._request_post(method, ca_request)
            print("SUCCESS: Received response")
            # print(response)
    except Exception as e:
        print(f"FAILED: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"Status: {e.response.status_code}")
             try:
                 print(f"Detail: {e.response.text}")
             except:
                 pass

# Case 1: Empty contents (Current implementation)
payload_empty_contents = {
    "contents": [],
    "systemInstruction": {
        "role": "system",
        "parts": [{"text": "You are a helpful assistant.\n\nUser:\nHello"}]
    },
    "generationConfig": {"temperature": 0.7}
}

# Case 2: Non-empty contents (Standard)
payload_standard = {
    "contents": [
        {"role": "user", "parts": [{"text": "Hello"}]}
    ],
    "systemInstruction": {
        "role": "system",
        "parts": [{"text": "You are a helpful assistant."}]
    },
    "generationConfig": {"temperature": 0.7}
}

if __name__ == "__main__":
    print("Starting reproduction tests...")
    
    models = ["gemini-3-flash-preview", "gemini-2.0-flash-exp", "gemini-1.5-pro-preview-0409"]

    for model in models:
        # Test Case 1 (Empty Contents - Current)
        test_payload("Empty Contents", payload_empty_contents, stream=False, model=model)
        
        # Test Case 2 (Standard Contents)
        test_payload("Standard Contents", payload_standard, stream=False, model=model)
