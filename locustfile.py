from locust import HttpUser, task, between
import uuid

class EduFlowUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.username = f"tester{uuid.uuid4().hex[:8]}"
        self.password = "testerpass"

        # Регистрация
        resp = self.client.post("/api/v1/register/", json={
            "username": self.username,
            "password": self.password,
            "email": f"{self.username}@example.com",
            "preferred_region": "Moscow"
        })
        if resp.status_code != 201:
            print(f"Registration failed for {self.username}: {resp.status_code} - {resp.text}")
            self.access_token = None
            return
        
        # Логин
        resp = self.client.post("/api/v1/token/", json={
            "username": self.username,
            "password": self.password
        })

        data = resp.json()
        self.access_token = data.get("access")
        if not self.access_token:
            print("No access token")
            return
        self.headers = {"Authorization": f"Bearer {self.access_token}"}

        # Получить список доступных должностей
        resp = self.client.get("/api/v1/job-targets/", headers=self.headers)
        if resp.status_code != 200:
            print(f"Failed to get job targets: {resp.status_code}")
            self.target_id = None
            return
        jobs = resp.json()
        if not jobs:
            print("No job targets available")
            self.target_id = None
            return
        first_job_id = jobs[0]['id']

        # Создать цель пользователя
        resp = self.client.post("/api/v1/user-targets/", 
                                json={"target_job_id": first_job_id},
                                headers=self.headers)
        if resp.status_code == 201:
            self.target_id = resp.json()['id']
            print(f"Created new user target with id {self.target_id}")
        else:
            print(f"Failed to create user target: {resp.status_code} - {resp.text}")
            self.target_id = None

    @task(5)
    def generate_path(self):
        if not self.access_token or not self.target_id:
            return
        resp = self.client.post("/api/v1/generate-path/", 
                                json={"job_target_id": self.target_id},
                                headers=self.headers)
        if resp.status_code != 200:
            print(f"Generate path failed: {resp.status_code} - {resp.text}")
