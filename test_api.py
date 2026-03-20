<<<<<<< HEAD
import requests

url = "http://localhost:8080/api/login"

data = {
    "username": "faculty1",
    "password": "faculty123"
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.json())
=======
import requests

url = "http://localhost:8080/api/login"

data = {
    "username": "faculty1",
    "password": "faculty123"
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.json())
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
