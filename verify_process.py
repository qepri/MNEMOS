import requests
import time
import sys

BASE_URL = "http://localhost:5000/api/documents"
FILE_PATH = "media/Guia Básica - Predicción de Anomalías.pdf"

def verify_process():
    print(f"Starting verification for {FILE_PATH}...")
    
    # Check if backend is up
    try:
        requests.get(BASE_URL)
        print("Backend is responding.")
    except Exception as e:
        print(f"Error connecting to backend: {e}")
        return

    # Upload
    files = {'file': open(FILE_PATH, 'rb')}
    print(f"Uploading {FILE_PATH}...")
    try:
        r = requests.post(f"{BASE_URL}/upload", files=files)
        if r.status_code != 201:
            print(f"Upload failed: {r.status_code} - {r.text}")
            return
    except Exception as e:
        print(f"Upload exceptions: {e}")
        return
        
    data = r.json()
    doc_id = data.get("id")
    print(f"Upload successful. Document ID: {doc_id}")
    
    # Poll Status
    print("Polling status...")
    start_time = time.time()
    
    while time.time() - start_time < 60: # 1 minute timeout
        try:
            r = requests.get(f"{BASE_URL}/{doc_id}/status")
            if r.status_code == 200:
                status_data = r.json()
                status = status_data.get("status")
                error = status_data.get("error")
                
                print(f"Status: {status}")
                
                if status == 'completed':
                    print("SUCCESS: Processing completed!")
                    return
                if status == 'error':
                    print(f"FAILURE: Processing failed with error: {error}")
                    return
                    
            time.sleep(2)
        except Exception as e:
             print(f"Polling error: {e}")
             time.sleep(2)
             
    print("TIMEOUT: Processing did not complete in 60 seconds.")

if __name__ == "__main__":
    verify_process()
