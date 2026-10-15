import requests

url = "https://api.ojp.gov/bjsdataset/v1/gcuy-rt5g.json"

response = requests.get(
    url,
    params={"$limit": 100000}, # there are 68852 total records
    timeout=30
)

response.raise_for_status()

data = response.json()

print("Status:", response.status_code)
print("Records:", len(data))
print("Columns:", list(data[0].keys()))
