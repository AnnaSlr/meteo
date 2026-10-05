from datetime import datetime
from io import StringIO

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}

POLLEN_NAMES = {
    "kaalnud1": "alder",
    "kabetud1": "birch",
    "kacoryd1": "hazel",
    "kafagud1": "beech",
    "kafraxd1": "ash",
    "kaquerd1": "oak",
    "khpoacd1": "grass",
}


def fetch_pollen_stations() -> pd.DataFrame:
    """
    Fetch the list of MeteoSwiss pollen monitoring stations.

    Returns
    -------
    pd.DataFrame
        Columns: code, name, canton, elevation, latitude, longitude.
    """
    url = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-pollen/ogd-pollen_meta_stations.csv"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    stations_df = pd.read_csv(StringIO(response.text), sep=";")

    return stations_df[
        [
            "station_abbr",
            "station_name",
            "station_canton",
            "station_height_masl",
            "station_coordinates_wgs84_lat",
            "station_coordinates_wgs84_lon",
        ]
    ].rename(
        columns={
            "station_abbr": "code",
            "station_name": "name",
            "station_canton": "canton",
            "station_height_masl": "elevation",
            "station_coordinates_wgs84_lat": "latitude",
            "station_coordinates_wgs84_lon": "longitude",
        }
    )


def fetch_pollen_parameters() -> dict:
    """
    Fetch metadata (description, unit) for each pollen type, from
    MeteoSwiss's parameter catalog. Mirrors the shape of weather.py's
    WEATHER_PARAMETERS, but sourced live from the API rather than hardcoded.

    Returns
    -------
    dict
        {pollen_name: {"description": ..., "unit": ...}}, e.g.
        {"birch": {"description": "Birch; daily average ...", "unit": "No/m³"}}.
    """
    url = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-pollen/ogd-pollen_meta_parameters.csv"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    params_df = pd.read_csv(StringIO(response.text), sep=";")

    d1_params = params_df[params_df["parameter_shortname"].isin(POLLEN_NAMES.keys())]

    return {
        POLLEN_NAMES[row["parameter_shortname"]]: {
            "description": row["parameter_description_en"],
            "unit": row["parameter_unit"],
        }
        for _, row in d1_params.iterrows()
    }


def fetch_pollen_measurements(station_code: str, granularity: str = "d") -> pd.DataFrame:
    """
    Fetch pollen measurements for one station.

    Parameters
    ----------
    station_code : str
        3-letter station code, e.g. "PLS" for Lausanne.
    granularity : str
        "h" for hourly, "d" for daily.

    Returns
    -------
    pd.DataFrame
        Raw measurement data, with one row per day/hour and one column
        per pollen parameter code (e.g. "kaalnud1").
    """
    code = station_code.lower()
    url = (
        f"https://data.geo.admin.ch/ch.meteoschweiz.ogd-pollen/{code}/"
        f"ogd-pollen_{code}_{granularity}_recent.csv"
    )
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), sep=";")


def fetch_pollen_for_day(
    day: datetime, station_codes: list | None = None
) -> tuple[pd.DataFrame, dict]:
    """
    Fetch real (station-measured) pollen concentrations for a single day,
    across MeteoSwiss's pollen monitoring network.

    Parameters
    ----------
    day : datetime
        The day to fetch data for.
    station_codes : list of str, optional
        3-letter station codes. Defaults to all 15 Swiss stations.

    Returns
    -------
    tuple
        (pollen_df, units) where pollen_df has one row per station, with
        columns: code, name, canton, elevation, latitude, longitude, and
        one column per pollen type (alder, birch, ...); units maps each
        pollen name to its unit (e.g. {"birch": "No/m³"}).
    """
    stations_df = fetch_pollen_stations()
    if station_codes is None:
        station_codes = stations_df["code"].tolist()

    rows = []
    for code in station_codes:
        measurements_df = fetch_pollen_measurements(code, granularity="d")
        measurements_df["reference_timestamp"] = pd.to_datetime(
            measurements_df["reference_timestamp"], format="%d.%m.%Y %H:%M"
        )
        day_row = measurements_df[measurements_df["reference_timestamp"].dt.date == day.date()]
        if day_row.empty:
            continue

        d1_cols = [c for c in measurements_df.columns if c.endswith("d1")]
        row = {"code": code}
        row.update(day_row[d1_cols].iloc[0].to_dict())
        rows.append(row)

    pollen_df = pd.DataFrame(rows)

    if pollen_df.empty:
        raise ValueError(
            f"No pollen data found for {day.date()}. "
            "Note: the '_recent' files only cover the current year; "
            "older dates require the '_historical' files (not yet supported)."
        )

    pollen_df = pollen_df.rename(columns=POLLEN_NAMES)

    parameters = fetch_pollen_parameters()
    units = {name: info["unit"] for name, info in parameters.items()}

    return stations_df.merge(pollen_df, on="code"), units