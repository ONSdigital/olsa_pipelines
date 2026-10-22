import pandas as pd
import requests

SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"

SEARCH_PARAMS = {
    "q": 'tags:"LAD" AND tags:"Output Area"',
    "sortField": "modified",
    "sortOrder": "desc",
    "num": 1000,
    "f": "json",
}

DATA_PARAMS = {"returnCountOnly": False,
               "outFields": "*",
               "f": "geoJSON",
               "where": "1=1",
               "resultOffset": 0}


def get_open_geo_data(url: str, query_params: dict):
    response = requests.get(url, params=query_params)
    if response.ok:
        content = response.json()
        return content
    else:
        raise requests.RequestException(
            f"HTTP Code: {response.status_code}, Status: {response.reason}")


def get_most_recent_data(json):
    for item in json["results"]:
        title = item["title"]

        if "Output Area" in title and "LAD" in title:
            print(f"Loading {title}")
            return item


def main():
    content = get_open_geo_data(SEARCH_URL, SEARCH_PARAMS)
    content = get_most_recent_data(content)

    list_of_dicts = []
    more_pages = True
    while more_pages:
        print(f"Loading page {DATA_PARAMS['resultOffset']}")
        paginated_data = get_open_geo_data(f"{content['url']}/0/query", query_params=DATA_PARAMS)

        # Extract relevant row information
        list_of_dicts.extend([field["properties"] for field in paginated_data["features"]])

        try:
            more_pages = paginated_data['properties']['exceededTransferLimit']
            DATA_PARAMS['resultOffset'] += len(paginated_data["features"])
        except KeyError:
            more_pages = False

    final_dataframe = pd.DataFrame(list_of_dicts)

main()
