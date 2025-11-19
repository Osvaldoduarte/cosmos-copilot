import requests
import json

BASE_URL = "http://localhost:8000"
USERNAME = "vendedor1"
PASSWORD = "senha123"

def login():
    url = f"{BASE_URL}/token"
    data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    print(f"Logging in as {USERNAME}...")
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            print("Login successful!")
            return token
        else:
            print(f"Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def get_conversations(token):
    url = f"{BASE_URL}/conversations"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Fetching conversations from {url}...")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        conversations = data.get("conversations", [])
        print(f"Found {len(conversations)} conversations.")
        for c in conversations:
            print(f" - {c['name']} ({c['id']}): Last msg: {c['lastMessage']}")
        return conversations
    else:
        print(f"Error fetching conversations: {response.status_code} - {response.text}")
        return []

def get_messages(token, jid):
    url = f"{BASE_URL}/conversations/{jid}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Fetching messages for {jid} from {url}...")
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        messages = response.json()
        print(f"Found {len(messages)} messages.")
        for m in messages:
            print(f" [{m['timestamp']}] {m['sender']}: {m['content']}")
    else:
        print(f"Error fetching messages: {response.status_code} - {response.text}")

if __name__ == "__main__":
    token = login()
    if token:
        conversations = get_conversations(token)
        
        # Test with the known JID
        target_jid = "554192235407@s.whatsapp.net"
        get_messages(token, target_jid)
