import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("MONDAY_API_TOKEN")
headers = {
    "Authorization": token,
    "Content-Type": "application/json",
    "API-Version": "2023-10"
}

# Mutation using the suggested name update_status_managed_column
query = """
mutation {
  update_status_managed_column (
    board_id: 18413482266,
    id: "color_mm3dtq01",
    settings: {
      labels: [
        { color: "orange", label: "Em andamento", index: 0 },
        { color: "green", label: "Positivo", index: 1 },
        { color: "red", label: "Negativo", index: 2 },
        { color: "blue", label: "Neutro", index: 3 },
        { color: "purple", label: "Inconclusivo", index: 4 }
      ]
    }
  ) {
    id
    title
  }
}
"""

response = requests.post(
    "https://api.monday.com/v2",
    json={"query": query},
    headers=headers
)

print(f"Status Code: {response.status_code}")
print(response.text)
