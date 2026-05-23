# visualization/map_renderer.py

import folium
import os
from config import OUTPUT_MAP_PATH


def render_route(G, result, source_lat, source_lon,
                 dest_lat, dest_lon):

    path           = result["path"]
    charging_stops = result["charging_stops"]
    route_type     = result["route_type"]
    total_time     = result["total_time_min"]
    total_kwh      = result["total_kwh"]
    total_soc      = result["total_soc_used"]

    # ── Base Map ───────────────────────────────────────────────────────
    center_lat = (source_lat + dest_lat) / 2
    center_lon = (source_lon + dest_lon) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=14,
        tiles="OpenStreetMap"
    )

    # ── Color based on route type ──────────────────────────────────────
    color = "blue" if route_type == "direct" else "red"
    if route_type == "rerouted":
        color = "purple"

    # ── Route Polyline ─────────────────────────────────────────────────
    route_coords = []
    for node in path:
        if node in G.nodes:
            node_data = G.nodes[node]
            lat = node_data.get("y", None)
            lon = node_data.get("x", None)
            if lat is not None and lon is not None:
                route_coords.append((lat, lon))

    print(f"Route has {len(path)} nodes, {len(route_coords)} valid coordinates.")

    if len(route_coords) >= 2:
        folium.PolyLine(
            locations=route_coords,
            color=color,
            weight=6,
            opacity=0.9,
            tooltip=f"{route_type.upper()} | {total_time} min | {total_kwh} kWh"
        ).add_to(m)
    else:
        print("⚠️ Not enough coordinates to draw route.")

    # ── Source Marker ──────────────────────────────────────────────────
    folium.Marker(
        location=[source_lat, source_lon],
        popup=folium.Popup(
            f"<b>START</b><br>SoC: {result.get('start_soc_pct', '?')}%",
            max_width=200
        ),
        icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(m)

    # ── Destination Marker ─────────────────────────────────────────────
    folium.Marker(
        location=[dest_lat, dest_lon],
        popup=folium.Popup(
            f"<b>DESTINATION</b><br>"
            f"Time: {total_time} min<br>"
            f"Energy: {total_kwh} kWh<br>"
            f"SoC used: {total_soc}%",
            max_width=200
        ),
        icon=folium.Icon(color="red", icon="flag", prefix="fa")
    ).add_to(m)

    # ── Charging Stop Markers ──────────────────────────────────────────
    for station in charging_stops:
        folium.Marker(
            location=[station["lat"], station["lon"]],
            popup=folium.Popup(
                f"<b>⚡ {station['name']}</b><br>"
                f"Type: {station['charger_type']}<br>"
                f"Rate: {station['rate_kw']} kW",
                max_width=250
            ),
            icon=folium.Icon(color="orange", icon="bolt", prefix="fa")
        ).add_to(m)

    # ── All Charging Stations (grey) ───────────────────────────────────
    all_stations = result.get("all_stations", [])
    for station in all_stations:
        if any(s["name"] == station["name"] for s in charging_stops):
            continue
        folium.CircleMarker(
            location=[station["lat"], station["lon"]],
            radius=6,
            color="gray",
            fill=True,
            fill_color="gray",
            fill_opacity=0.5,
            popup=folium.Popup(
                f"<b>{station['name']}</b><br>"
                f"Type: {station['charger_type']}<br>"
                f"Rate: {station['rate_kw']} kW",
                max_width=250
            )
        ).add_to(m)

    # ── Info Box ───────────────────────────────────────────────────────
    info_html = f"""
    <div style="
        position: fixed;
        top: 10px; right: 10px;
        z-index: 1000;
        background: white;
        padding: 12px 16px;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
        font-size: 13px;
        min-width: 200px;
    ">
        <b style="font-size:15px;">🚗 EV Route Summary</b><br><br>
        <b>Type:</b> {route_type.replace('_', ' ').title()}<br>
        <b>Time:</b> {total_time} min<br>
        <b>Energy:</b> {total_kwh} kWh<br>
        <b>SoC used:</b> {total_soc}%<br>
        {'<b>⚡ Charging stop:</b> ' + charging_stops[0]['name'] if charging_stops else '<b>✅ No charging needed</b>'}
    </div>
    """
    m.get_root().html.add_child(folium.Element(info_html))

    # ── Save ───────────────────────────────────────────────────────────
    os.makedirs("output", exist_ok=True)
    m.save(OUTPUT_MAP_PATH)
    print(f"Map saved to {OUTPUT_MAP_PATH}")
    print("Open output/route_map.html in your browser to view.")

    return m


if __name__ == "__main__":
    print("Run main.py to generate a route map.")