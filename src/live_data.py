"""
Live external data connectors. Each function is a REAL, working call to
a real public API -- not a stub -- but every one degrades gracefully
(returns None / an explanatory dict) if no API key is configured or the
service is unreachable, so the app never fabricates a "live" number.

Required keys (all free tier):
  DATA_GOV_IN_API_KEY  - register at https://data.gov.in/user/register
                          -> "My Account" -> "API Keys". Used for mandi
                          prices (Agmarknet) and district crop stats.
  SENTINEL_HUB_CLIENT_ID / SENTINEL_HUB_CLIENT_SECRET
                        - free account at https://www.sentinel-hub.com/
                          -> Dashboard -> "OAuth clients". Used for NDVI.
  NEWSAPI_KEY          - free account at https://newsapi.org/register
                          Used for the agri-news feed.

Set these as environment variables or Streamlit secrets. Never hardcode
an API key in source control.
"""

import os
from datetime import date, timedelta
from xml.etree import ElementTree
from urllib.parse import parse_qs, urlparse
import requests

MANDI_RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"  # data.gov.in
AGMARKNET_API = "https://api.agmarknet.gov.in/v1"
AGMARKNET_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://agmarknet.gov.in",
    "Referer": "https://agmarknet.gov.in/",
}
def _data_gov_key(api_key=None):
    value = (api_key or os.environ.get("DATA_GOV_IN_API_KEY") or "").strip()
    if "api-key=" in value:
        parsed = parse_qs(urlparse(value).query)
        value = parsed.get("api-key", [value])[0]
    return value.strip().strip('"').strip("'")


def _api_error(response):
    try:
        payload = response.json()
        detail = payload.get("error_description") or payload.get("error")
    except ValueError:
        detail = response.text.strip()
    if response.status_code == 403:
        detail = detail or "The API key was rejected or is not active."
    return f"HTTP {response.status_code}: {detail or 'The API request was rejected.'}"


def get_agmarknet_daily_prices(
    arrival_date: str,
    district: str = None,
    state_id: int = 26,
):
    """Fetch official Agmarknet daily prices without a data.gov.in key."""
    try:
        params = {"date": arrival_date, "stateIds": state_id, "includeExcel": "false"}
        report = requests.get(
            f"{AGMARKNET_API}/prices-and-arrivals/commodity-wise/daily-report-state",
            params=params,
            headers=AGMARKNET_HEADERS,
            timeout=20,
        )
        report.raise_for_status()
        payload = report.json()
        if not payload.get("success"):
            return {"error": "agmarknet_error", "note": payload.get("message", "Agmarknet returned no data.")}

        market_names = None
        if district and district != "All Odisha":
            market_response = requests.get(
                f"{AGMARKNET_API}/market-district-state",
                headers=AGMARKNET_HEADERS,
                timeout=20,
            )
            market_response.raise_for_status()
            market_names = {
                item["market_name"]
                for item in market_response.json()
                if item.get("state_id") == state_id and item.get("district_name") == district
            }

        records = []
        for market in payload.get("markets", []):
            if market_names is not None and market.get("marketName") not in market_names:
                continue
            for group in market.get("commodityGroups", []):
                for commodity in group.get("commodities", []):
                    for item in commodity.get("data", []):
                        records.append({
                            "arrival_date": arrival_date,
                            "district": district or "Odisha",
                            "market": market.get("marketName", ""),
                            "commodity": commodity.get("commodityName", ""),
                            "variety": item.get("variety", ""),
                            "min_price": item.get("minimumPrice"),
                            "max_price": item.get("maximumPrice"),
                            "modal_price": item.get("modalPrice"),
                            "price_unit": item.get("unitOfPrice", ""),
                            "arrivals": item.get("arrivals"),
                            "arrival_unit": item.get("unitOfArrivals", ""),
                            "_matched_arrival_date": arrival_date,
                        })
        return records
    except (requests.RequestException, ValueError, KeyError) as exc:
        return {
            "error": "agmarknet_unavailable",
            "note": f"Agmarknet request failed: {exc}",
        }


def check_mandi_connection(api_key: str = None):
    """Check the mandi endpoint without downloading the full price table."""
    key = _data_gov_key(api_key)
    if not key:
        return {
            "ok": False,
            "error": "missing_api_key",
            "note": "Enter the data.gov.in API key first.",
        }
    params = {
        "api-key": key,
        "format": "json",
        "limit": 1,
        "filters[state.keyword]": "Odisha",
    }
    try:
        response = requests.get(
            f"https://api.data.gov.in/resource/{MANDI_RESOURCE_ID}",
            params=params,
            timeout=12,
        )
        if not response.ok:
            return {
                "ok": False,
                "error": "http_error",
                "note": _api_error(response),
            }
        payload = response.json()
        if payload.get("error"):
            return {
                "ok": False,
                "error": payload["error"],
                "note": payload.get(
                    "error_description",
                    "The data.gov.in API rejected this key.",
                ),
            }
        return {"ok": True, "record_count": len(payload.get("records", []))}
    except (requests.RequestException, ValueError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "note": "The API could not be reached. Check the internet connection "
                    "and data.gov.in availability.",
        }


def get_mandi_price(
    commodity: str = None,
    state: str = "Odisha",
    district: str = None,
    arrival_date: str = None,
    api_key: str = None,
    limit: int = 1000,
    previous_days: int = 7,
):
    """
    Real-time (as reported to Agmarknet) mandi min/max/modal price for a
    commodity (or all commodities when omitted), filtered to Odisha by default. Returns a list of record
    dicts, or {'error': ...} if the call failed.
    """
    params = {
        "api-key": _data_gov_key(api_key),
        "format": "json",
        "limit": max(limit, 100),
        "filters[state.keyword]": state,
    }
    if commodity:
        params["filters[commodity]"] = commodity
    if district:
        params["filters[district]"] = district
    if not params["api-key"]:
        return {
            "error": "missing_api_key",
            "note": "Enter the data.gov.in key in the app or configure DATA_GOV_IN_API_KEY.",
        }
    try:
        resp = requests.get(
            f"https://api.data.gov.in/resource/{MANDI_RESOURCE_ID}",
            params=params, timeout=12,
        )
        if not resp.ok:
            return {
                "error": "http_error",
                "note": _api_error(resp),
            }
        data = resp.json()
        if data.get("error"):
            return {
                "error": data["error"],
                "note": data.get("error_description", "The data.gov.in API rejected the request."),
            }
        records = data.get("records", [])
        if not arrival_date:
            for record in records:
                record["_matched_arrival_date"] = None
            return records

        requested = date.fromisoformat(arrival_date)
        search_dates = [
            (requested - timedelta(days=offset)).isoformat()
            for offset in range(previous_days + 1)
        ]
        for search_date in search_dates:
            matching = [
                record for record in records
                if str(record.get("arrival_date", record.get("Arrival_Date", ""))).startswith(search_date)
            ]
            if matching:
                for record in matching:
                    record["_matched_arrival_date"] = search_date
                return matching
        return []
    except (requests.RequestException, ValueError) as e:
        return {"error": str(e), "note": "Live mandi price unavailable -- "
                "check the API key, internet connection, or Agmarknet availability."}


def get_sentinel_ndvi(lat: float, lon: float, start_date: str, end_date: str):
    """
    Mean NDVI for a small bounding box around (lat, lon) over a date
    range, via the Sentinel Hub Statistical API (Sentinel-2 L2A).
    Requires SENTINEL_HUB_CLIENT_ID/SECRET. Returns a dict or an
    explanatory error dict if not configured / unreachable.
    """
    client_id = os.environ.get("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.environ.get("SENTINEL_HUB_CLIENT_SECRET")
    if not client_id or not client_secret:
        return {"error": "not_configured", "note": "Set SENTINEL_HUB_CLIENT_ID / "
                "SENTINEL_HUB_CLIENT_SECRET to enable live NDVI. Falling back to "
                "the historical NDVI in the NDVI-repo dataset for this district."}
    try:
        token_resp = requests.post(
            "https://services.sentinel-hub.com/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret), timeout=8,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]

        d = 0.01  # ~1km box around the point
        bbox = [lon - d, lat - d, lon + d, lat + d]
        payload = {
            "input": {
                "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                "data": [{"type": "sentinel-2-l2a"}],
            },
            "aggregation": {
                "timeRange": {"from": f"{start_date}T00:00:00Z", "to": f"{end_date}T23:59:59Z"},
                "aggregationInterval": {"of": "P1D"},
                "evalscript": (
                    "//VERSION=3\nfunction setup(){return {input:['B04','B08','dataMask'],"
                    "output:[{id:'ndvi',bands:1},{id:'dataMask',bands:1}]};}"
                    "function evaluatePixel(s){let ndvi=(s.B08-s.B04)/(s.B08+s.B04);"
                    "return {ndvi:[ndvi],dataMask:[s.dataMask]};}"
                ),
            },
        }
        resp = requests.post(
            "https://services.sentinel-hub.com/api/v1/statistics",
            json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_live_weather(lat: float, lon: float):
    """
    REAL live weather + rainfall for any lat/lon, via Open-Meteo --
    a free public API that needs NO key and no registration, so this
    one is live right now with zero setup. Returns current conditions
    plus today's/last-7-days precipitation.
    """
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
                "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
                "past_days": 7, "forecast_days": 7, "timezone": "auto",
            },
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_agri_news(query: str = "Odisha agriculture", page_size: int = 8, api_key: str = None):
    """
    Recent news headlines relevant to Odisha agriculture, via NewsAPI.org.
    Requires NEWSAPI_KEY.
    """
    api_key = api_key or os.environ.get("NEWSAPI_KEY")
    if not api_key:
        try:
            resp = requests.get(
                "https://news.google.com/rss/search",
                params={"q": f"{query} when:7d", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
                timeout=8,
            )
            resp.raise_for_status()
            root = ElementTree.fromstring(resp.content)
            articles = []
            for item in root.findall("./channel/item")[:page_size]:
                articles.append({
                    "title": item.findtext("title", default=""),
                    "url": item.findtext("link", default=""),
                    "source": {"name": "Google News RSS"},
                    "publishedAt": item.findtext("pubDate", default=""),
                })
            return articles
        except Exception as exc:
            return {"error": "not_configured", "note": f"NewsAPI is not configured and RSS fallback failed: {exc}"}
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={"q": query, "language": "en", "sortBy": "publishedAt",
                    "pageSize": page_size, "apiKey": api_key},
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json().get("articles", [])
    except Exception as e:
        return {"error": str(e)}
