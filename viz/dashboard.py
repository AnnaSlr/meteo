import re
import json

import folium
import pandas as pd
from branca.colormap import LinearColormap
from folium import FeatureGroup, LayerControl

WEATHER_LAYERS = [
    ("tavg", "Temperature", ["blue", "yellow", "red"]),
    ("prcp", "Precipitation", ["white", "lightblue", "blue"]),
    ("snow", "Snowfall", ["white", "lightblue", "blue"]),
    ("wspd", "Wind speed", ["white", "red"]),
]

POLLUTION_LAYERS = [
    ("no2", "NO2", ["white", "red"]),
    ("o3", "O3", ["white", "red"]),
    ("pm10", "PM10", ["white", "red"]),
    ("pm25", "PM25", ["white", "red"]),
    ("so2", "SO2", ["white", "red"]),
]

POLLEN_LAYERS = [
    ("alder", "Alder", ["white", "red"]),
    ("birch", "Birch", ["white", "red"]),
    ("hazel", "Hazel", ["white", "red"]),
    ("beech", "Beech", ["white", "red"]),
    ("grass", "Grass", ["white", "red"]),
    ("ash", "Ash", ["white", "red"]),
    ("oak", "Oak", ["white", "red"]),
]


def _slug(label: str) -> str:
    """Turn a layer label into a safe HTML id fragment."""
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def add_layer(
    m: folium.Map,
    df: pd.DataFrame,
    param: str,
    label: str,
    colors: list,
    units: dict,
) -> dict | None:
    """
    Add one color-coded circle-marker layer to a Folium map, and return
    the HTML for a matching custom legend (not drawn on the map itself).

    Returns
    -------
    dict or None
        {"label": label, "id": html_id, "html": legend_html_snippet},
        or None if the layer had no data.
    """
    clean_df = df.dropna(subset=[param])
    if clean_df.empty:
        return None

    unit = units[param]
    vmin, vmax = float(clean_df[param].min()), float(clean_df[param].max())
    colormap = LinearColormap(colors, vmin=vmin, vmax=vmax)

    layer = FeatureGroup(name=label)
    for _, row in clean_df.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=7,
            color=colormap(float(row[param])),
            fill=True,
            fill_opacity=0.8,
            tooltip=f"{row['name']}: {row[param]} {unit}",
        ).add_to(layer)
    layer.add_to(m)

    gradient_css = f"linear-gradient(to right, {', '.join(colors)})"
    legend_id = f"legend-{_slug(label)}"
    legend_html = f"""
    <div id="{legend_id}" style="margin-bottom:8px;">
        <b>{label} ({unit})</b>
        <div style="height:12px; background:{gradient_css}; margin:3px 0; border-radius:2px;"></div>
        <span style="float:left;">{vmin:.1f}</span>
        <span style="float:right;">{vmax:.1f}</span>
        <div style="clear:both;"></div>
    </div>
    """

    return {"label": label, "id": legend_id, "html": legend_html}


def build_dashboard(
    weather_df: pd.DataFrame | None,
    units_weather: dict | None,
    pollution_df: pd.DataFrame | None,
    units_pollution: dict | None,
    pollen_df: pd.DataFrame | None,
    units_pollen: dict | None,
    output_path: str = "outputs/dashboard.html",
    center: tuple = (46.8, 8.2),
) -> str:
    """
    Build a multi-layer Folium dashboard from weather, air quality and
    pollen data. Any source can be omitted by passing its DataFrame as None.
    """
    m = folium.Map(location=list(center), zoom_start=8)

    legends = []

    def add_group(df, layers, units):
        if df is None:
            return
        for param, label, colors in layers:
            legend = add_layer(m, df, param, label, colors, units)
            if legend is not None:
                legends.append(legend)

    add_group(weather_df, WEATHER_LAYERS, units_weather)
    add_group(pollution_df, POLLUTION_LAYERS, units_pollution)
    add_group(pollen_df, POLLEN_LAYERS, units_pollen)

    LayerControl(collapsed=False).add_to(m)

    # All legends in one fixed container. Step 2: always visible for now,
    # no checkbox sync yet.
    legend_box = "".join(legend["html"] for legend in legends)
    container_html = f"""
    <div id="legend-container" style="
        position: fixed; bottom: 20px; left: 20px; z-index: 9999;
        background: white; padding: 10px; border: 2px solid grey;
        border-radius: 6px; font-size: 13px; width: 220px;
        max-height: 70vh; overflow-y: auto;">
        {legend_box}
    </div>
    """
    m.get_root().html.add_child(folium.Element(container_html))

    legend_by_label = {legend["label"]: legend["id"] for legend in legends}
    js = f"""
    window.addEventListener('load', function() {{
        var legendByLabel = {json.dumps(legend_by_label)};

        function toggle(name, show) {{
            var id = legendByLabel[name];
            if (!id) return;
            var el = document.getElementById(id);
            if (el) el.style.display = show ? 'block' : 'none';
        }}

        for (var name in legendByLabel) {{
            toggle(name, true);
        }}

        {m.get_name()}.on('overlayadd', function(e) {{ toggle(e.name, true); }});
        {m.get_name()}.on('overlayremove', function(e) {{ toggle(e.name, false); }});
    }});
    """
    m.get_root().script.add_child(folium.Element(js))

    m.save(output_path)

    return output_path