# -- bash ----------------------------
# python -m pip install --upgrade pip
# python -m venv .venv
# .venv\Scripts\activate
# pip install -r requirements.txt

from datetime import datetime

from data.pollen import fetch_pollen_for_day
from data.pollution import fetch_air_quality_for_day
from data.weather import fetch_weather_for_day
from viz.dashboard import build_dashboard

DAY = datetime(2026, 4, 15)
COUNTRY_ISO = "CH"
FETCH_WEATHER, FETCH_POLLUTION, FETCH_POLLEN = True, False, True


def run(day: datetime, country_iso: str) -> None:
    weather_df, units_weather = (None, None)
    if FETCH_WEATHER:
        print("Weather")
        weather_df, units_weather = fetch_weather_for_day(day, country_iso)

    pollution_df, units_pollution = (None, None)
    if FETCH_POLLUTION:
        print("Pollution")
        pollution_df, units_pollution = fetch_air_quality_for_day(day, country_iso)

    pollen_df, units_pollen = (None, None)
    if FETCH_POLLEN and country_iso == "CH":
        print("Pollen")
        pollen_df, units_pollen = fetch_pollen_for_day(day)

    output_path = build_dashboard(
        weather_df, units_weather,
        pollution_df, units_pollution,
        pollen_df, units_pollen,
    )
    print(f"Dashboard saved to {output_path}")


if __name__ == "__main__":
    run(DAY, COUNTRY_ISO)