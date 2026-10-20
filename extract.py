import json
import requests

url = "https://api.ojp.gov/bjsdataset/v1/gcuy-rt5g.json"

response = requests.get(
    url,
    params={"$limit": 100000}, # there are 68852 total records
    timeout=30
)

response.raise_for_status()

data = response.json()

log = {
    "Status": response.status_code,
    "Records": len(data),
    "Columns": list(data[0].keys())
}

json.dump(log, open("logs/extractionlog.json", "w"), indent=4)

print(log)