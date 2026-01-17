import os
from openai import OpenAI
import time

# Configuration matching the app (assuming default port 1234 for LM Studio)
BASE_URL = "http://localhost:1234/v1" 
API_KEY = "lm-studio"
MODEL = "qwen/qwen3-vl-4b" # Using the model seen in logs

print(f"Testing connection to {BASE_URL} with model {MODEL}...")

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY
)

try:
    start_time = time.time()
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello!"}
        ],
        temperature=0.7
    )
    end_time = time.time()
    
    print("\n--- Success! ---")
    print(f"Time taken: {end_time - start_time:.2f}s")
    print("Response:")
    print(response.choices[0].message.content)

except Exception as e:
    print("\n--- Failed! ---")
    print(e)
