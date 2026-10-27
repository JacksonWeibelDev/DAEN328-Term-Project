import requests

API_URL = "https://api.ojp.gov/bjsdataset/v1/gcuy-rt5g.json"


def extract_data(updated_since=None, page_size=1000, num_records=None):

    records = []
    offset = 0

    while True:

        # Determine how many records to request
        limit = page_size

        if num_records is not None:
            remaining = num_records - len(records)

            if remaining <= 0:
                break

            limit = min(page_size, remaining)

        # Build API request parameters
        params = {
            "$limit": limit,
            "$offset": offset,
            "$order": ":updated_at ASC, :id ASC",
            "$$exclude_system_fields": "false"
        }

        # Only retrieve updated records when a checkpoint exists
        # INCREMENTAL EXTRACTION STEP
        if updated_since is not None:
            params["$where"] = f":updated_at > '{updated_since}'"

        # Request data
        try:
            response = requests.get(
                API_URL,
                params=params,
                timeout=60
            )

            response.raise_for_status()
            page = response.json()

        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(
                f"NCVS API request failed: {error}"
            ) from error

        if not isinstance(page, list):
            raise RuntimeError("Unexpected API response format")

        if any(
            not isinstance(row, dict)
            or ":id" not in row
            or ":updated_at" not in row
            for row in page
        ):
            raise RuntimeError("Missing required NCVS system fields")

        # Add the current page to our records
        records.extend(page)

        print(f"Retrieved {len(page)} rows. Total: {len(records)}")

        # Move to the next page
        offset += len(page)

        # Stop when there are no more records
        if len(page) < limit:
            break

    return records