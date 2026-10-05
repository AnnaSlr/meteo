import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv

# https://docs.openaq.org/using-the-api/quick-start
# https://python.openaq.org/getting-started/resources/

load_dotenv()
API_KEY = os.getenv("API_KEY_openaq")
HEADERS = {"X-API-Key": API_KEY}


def get_all_stations(country_iso: str) -> list:
    """
    Get all official (reference monitor) OpenAQ stations for a country.

    Parameters
    ----------
    country_iso : str
        ISO 3166-1 alpha-2 country code, e.g. "CH" for Switzerland.

    Returns
    -------
    list of dict
        Raw location objects as returned by the API. Limited to 500
        stations per call (more than enough for a single country).
    """
    url = "https://api.openaq.org/v3/locations"
    params = {"iso": country_iso, "monitor": "true", "limit": 500}
    response = requests.get(url, params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()["results"]


def locations_to_sensors_df(locations: list) -> pd.DataFrame:
    """
    Flatten OpenAQ location objects into one row per sensor.

    Parameters
    ----------
    locations : list of dict
        Raw location objects, as returned by get_all_stations().

    Returns
    -------
    pd.DataFrame
        One row per sensor, with columns: location_id, name, latitude,
        longitude, sensor_id, parameter, units, display_name.
    """
    df = pd.json_normalize(
        locations,
        record_path="sensors",
        meta=[
            "id",
            "name",
            ["coordinates", "latitude"],
            ["coordinates", "longitude"],
        ],
        record_prefix="sensor_",
        meta_prefix="location_",
    )

    df = df.rename(
        columns={
            "location_id": "location_id",
            "location_name": "name",
            "location_coordinates.latitude": "latitude",
            "location_coordinates.longitude": "longitude",
            "sensor_parameter.name": "parameter",
            "sensor_parameter.units": "units",
            "sensor_parameter.displayName": "display_name",
        }
    )

    cols = [
        "location_id",
        "name",
        "latitude",
        "longitude",
        "sensor_id",
        "parameter",
        "units",
        "display_name",
    ]
    return df[cols]


def get_pollutant_parameters(official_df: pd.DataFrame) -> dict:
    """
    Build a {pollutant: {"description": ..., "unit": ...}} lookup from an
    already-fetched sensors DataFrame. Mirrors WEATHER_PARAMETERS
    (weather.py) and fetch_pollen_parameters() (pollen.py), but sourced
    from data already in memory rather than a separate request.

    Parameters
    ----------
    official_df : pd.DataFrame
        Output of locations_to_sensors_df().

    Returns
    -------
    dict
        {parameter: {"description": ..., "unit": ...}}, e.g.
        {"no2": {"description": "NO2 mass", "unit": "µg/m³"}}.
    """
    deduped = official_df.drop_duplicates("parameter")
    return {
        row["parameter"]: {"description": row["display_name"], "unit": row["units"]}
        for _, row in deduped.iterrows()
    }


def fetch_sensor_day(sensor_id: int, day: datetime) -> float | None:
    """
    Fetch the daily average value for one sensor, on one day.

    Returns None if no data is available for that day.
    """
    url = f"https://api.openaq.org/v3/sensors/{sensor_id}/days"
    params = {
        "date_from": day.strftime("%Y-%m-%d"),
        "date_to": (day + timedelta(days=1)).strftime("%Y-%m-%d"),
    }
    resp = requests.get(url, params=params, headers=HEADERS)
    if resp.status_code != 200:
        return None
    results = resp.json()["results"]
    if not results:
        return None
    return results[0]["value"]


def fetch_air_quality_for_day(
    day: datetime, country_iso: str = "CH"
) -> tuple[pd.DataFrame, dict]:
    """
    Fetch daily average pollutant values for all official stations in a
    country, for a single day. Mirrors fetch_weather_for_day()'s shape.

    Parameters
    ----------
    day : datetime
        The day to fetch data for.
    country_iso : str
        ISO 3166-1 alpha-2 country code.

    Returns
    -------
    tuple
        (wide_df, units) where wide_df has one row per station, with
        columns location_id, name, latitude, longitude, and one column per
        pollutant (no2, o3, pm10, ...); units maps each pollutant name to
        its unit (e.g. {"no2": "µg/m³"}).
    """
    locations = get_all_stations(country_iso)
    official_df = locations_to_sensors_df(locations)

    rows = []
    for _, sensor in official_df.iterrows():
        value = fetch_sensor_day(sensor["sensor_id"], day)
        if value is None:
            continue
        rows.append(
            {
                "location_id": sensor["location_id"],
                "name": sensor["name"],
                "latitude": sensor["latitude"],
                "longitude": sensor["longitude"],
                "parameter": sensor["parameter"],
                "value": value,
            }
        )
        time.sleep(0.15)

    long_df = pd.DataFrame(rows)

    if long_df.empty:
        raise ValueError(f"No air quality data retrieved for {day.date()} in {country_iso}")

    wide_df = long_df.pivot_table(
        index=["location_id", "name", "latitude", "longitude"],
        columns="parameter",
        values="value",
    ).reset_index()

    parameters = get_pollutant_parameters(official_df)
    units = {name: info["unit"] for name, info in parameters.items()}

    return wide_df, units