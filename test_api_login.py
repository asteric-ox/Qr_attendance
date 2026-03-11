import requests

BASE_URL = "http://127.0.0.1:8080/api"

def test_login():
    payload = {
        "username": "admin1",
        "password": "admin123",  # This is the default I seeded
        "device_id": "test_device"
    }
    try:
        response = requests.post(f"{BASE_URL}/login", json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login()
