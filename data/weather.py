from datetime import datetime

import meteostat as ms
import pandas as pd

# Meteostat (v1.17.0) exposes no endpoint or object carrying parameter
# units, unlike OpenAQ and MeteoSwiss. This table is transcribed by hand
# from https://dev.meteostat.net/parameters.

WEATHER_PARAMETERS = {
    "tavg": {"description": "Mean Air Temperature", "unit": "°C"},
    "tmin": {"description": "Mean Daily Minimum Air Temperature", "unit": "°C"},
    "tmax": {"description": "Mean Daily Maximum Air Temperature", "unit": "°C"},
    "prcp": {"description": "Total Precipitation", "unit": "mm"},
    "snow": {"description": "Snowfall", "unit": "cm"},
    "wdir": {"description": "Wind Direction", "unit": "°"},
    "wspd": {"description": "Average Wind Speed", "unit": "km/h"},
    "wpgt": {"description": "Peak Wind Gust", "unit": "km/h"},
    "pres": {"description": "Average Air Pressure (MSL)", "unit": "hPa"},
    "tsun": {"description": "Sunshine Duration", "unit": "min"},
}

WEATHER_UNITS = {code: info["unit"] for code, info in WEATHER_PARAMETERS.items()}


def get_all_stations(country_iso: str) -> pd.DataFrame:
    """
    Get all Meteostat stations for a given country.

    Parameters
    ----------
    country_iso : str
        ISO country code: "CH" for Switzerland, "FR" for France, etc.

    Returns
    -------
    pd.DataFrame
        DataFrame with station information (name, latitude, longitude,
        elevation, ...).
    """
    return ms.Stations().region(country_iso).fetch()


def fetch_weather_for_day(
    day: datetime, country_iso: str = "CH"
) -> tuple[pd.DataFrame, dict]:
    """
    Fetch daily weather measurements for all stations in a country, for a
    single day.

    Parameters
    ----------
    day : datetime
        The day to fetch data for (time part is ignored).
    country_iso : str
        ISO country code, e.g. "CH" for Switzerland.

    Returns
    -------
    tuple
        (merged_df, units) where merged_df has one row per station, with
        columns: station, time, tavg, tmin, tmax, prcp, snow, wdir, wspd,
        wpgt, pres, tsun, name, latitude, longitude, elevation; units maps
        each measurement code to its unit (e.g. {"tavg": "°C"}).
    """
    stations_df = get_all_stations(country_iso)
    daily_df = ms.Daily(stations_df, day, day).fetch()

    if daily_df.empty:
        raise ValueError(f"No weather data found for {day.date()} in {country_iso}")

    merged = daily_df.join(
        stations_df[["name", "latitude", "longitude", "elevation"]],
        on="station",
    )

    return merged, WEATHER_UNITS