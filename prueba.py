import requests

url = "https://bicimania.pythonanywhere.com/api/info"

headers = {
    "X-API-Key": "70037976"
}

response = requests.get(url, headers=headers)

print(response.status_code)
print(response.text)
