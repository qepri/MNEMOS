import requests
import sys

BASE_URL = "http://localhost:5000/api"

def verify_conversations_api():
    print("Testing Conversation API...")
    
    # 1. Create Conversation (implicitly or explicitly?)
    # Our Chat API creates it if missing, but we also have explicit create endpoint.
    print("1. Creating explicit conversation...")
    r = requests.post(f"{BASE_URL}/conversations/", json={"title": "Test Chat 1"})
    if r.status_code != 201:
        print(f"FAILED to create conversation: {r.text}")
        return
    conv1 = r.json()
    conv1_id = conv1['id']
    print(f"   Created ID: {conv1_id}")
    
    # 2. Add Message via Chat API
    print("2. Sending message to conversation...")
    payload = {
        "question": "Hello, who are you?",
        "conversation_id": conv1_id
    }
    r = requests.post(f"{BASE_URL}/chat/", json=payload)
    if r.status_code != 200:
        print(f"FAILED to chat: {r.text}")
        return
    resp = r.json()
    print(f"   Answer: {resp['answer'][:50]}...")
    
    # 3. List Conversations
    print("3. Listing conversations...")
    r = requests.get(f"{BASE_URL}/conversations/")
    if r.status_code != 200:
        print(f"FAILED to list: {r.text}")
        return
    convs = r.json()
    print(f"   Found {len(convs)} conversations.")
    found = any(c['id'] == conv1_id for c in convs)
    if not found:
        print("FAILED: Created conversation not found in list.")
        return
        
    # 4. Get specific conversation history
    print("4. Fetching history...")
    r = requests.get(f"{BASE_URL}/conversations/{conv1_id}")
    if r.status_code != 200:
        print(f"FAILED to get history: {r.text}")
        return
    history = r.json()
    msgs = history.get('messages', [])
    print(f"   History has {len(msgs)} messages.")
    if len(msgs) < 2: # User + Assistant
        print("FAILED: Expected at least 2 messages.")
        return
        
    # 5. Search
    print("5. Searching...")
    r = requests.get(f"{BASE_URL}/conversations/?search=Test")
    if r.status_code != 200:
        print(f"FAILED to search: {r.text}")
        return
    results = r.json()
    print(f"   Search found {len(results)} matches.")
    
    print("\nSUCCESS: All API tests passed.")

if __name__ == "__main__":
    verify_conversations_api()
