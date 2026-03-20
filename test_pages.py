<<<<<<< HEAD
import requests

BASE_URL = "http://127.0.0.1:8080"

def test_pages():
    pages = ["/login.html", "/admin_dashboard.html", "/admin.html"]
    for page in pages:
        response = requests.get(f"{BASE_URL}{page}")
        print(f"Page: {page}, Status: {response.status_code}, Length: {len(response.text)}")

if __name__ == "__main__":
    test_pages()
=======
import requests

BASE_URL = "http://127.0.0.1:8080"

def test_pages():
    pages = ["/login.html", "/admin_dashboard.html", "/admin.html"]
    for page in pages:
        response = requests.get(f"{BASE_URL}{page}")
        print(f"Page: {page}, Status: {response.status_code}, Length: {len(response.text)}")

if __name__ == "__main__":
    test_pages()
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
