<<<<<<< HEAD
from app import app

with app.test_client() as client:
    res = client.post("/api/admin/reports", json={
        "branch": "CSE",
        "semester": "S6",
        "subject": "CD",
        "period": "weekly"
    })

    print("Status:", res.status_code)
    print("Report:", res.get_json())
=======
from app import app

with app.test_client() as client:
    res = client.post("/api/admin/reports", json={
        "branch": "CSE",
        "semester": "S6",
        "subject": "CD",
        "period": "weekly"
    })

    print("Status:", res.status_code)
    print("Report:", res.get_json())
>>>>>>> cfc9b6af5e1d5697dd003ccf010269bd3f0df0de
