from locust import HttpUser, task, between, events
from locust_plugins.users.rest import RestUser


class Shopper(HttpUser):
    wait_time = between(1, 3)        # think‑time
    host = "https://api.example.com"

    def on_start(self):
        resp = self.client.post("/auth", json={"u": "demo", "p": "pass"})
        self.token = resp.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def browse(self):
        item = self.client.get("/items/random", headers=self.headers).json()
        self.item_id = item["id"]

    @task(1)
    def purchase(self):
        self.client.post("/order", json={"item_id": self.item_id}, headers=self.headers)

class Guest(HttpUser):
    wait_time = between(0.5, 2)
    host = "https://api.example.com"

    @task
    def list_items(self):
        self.client.get("/items")
