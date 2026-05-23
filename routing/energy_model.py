# routing/energy_model.py

from config import (
    BASE_CONSUMPTION_WH_PER_KM,
    GRADIENT_FACTOR,
    SPEED_FACTOR,
    REGEN_FACTOR,
    BATTERY_CAPACITY_KWH
)


def compute_edge_energy(length_km, speed_kmh, elevation_gain, elevation_loss):
    """
    Physics-based energy consumption for one edge.

    Formula:
        energy (Wh) = base_consumption × distance
                    + gradient_factor × elevation_gain
                    + speed_factor × speed²
                    - regen_factor × elevation_loss

    Args:
        length_km      : edge length in km
        speed_kmh      : travel speed in km/h
        elevation_gain : uphill meters on this edge
        elevation_loss : downhill meters on this edge (regeneration)

    Returns:
        energy_wh  : energy consumed in Wh (can be negative = net regen)
        energy_kwh : same in kWh
        soc_delta  : fraction of total battery consumed (negative = gained)
    """

    base       = BASE_CONSUMPTION_WH_PER_KM * length_km
    gradient   = GRADIENT_FACTOR * elevation_gain
    speed_cost = SPEED_FACTOR * (speed_kmh ** 2)
    regen      = REGEN_FACTOR * elevation_loss

    energy_wh  = base + gradient + speed_cost - regen
    energy_wh  = max(energy_wh, 0.0)          # can't gain more than you spend

    energy_kwh = energy_wh / 1000.0
    soc_delta  = energy_kwh / BATTERY_CAPACITY_KWH

    return energy_wh, energy_kwh, soc_delta


def compute_path_energy(G, path):
    """
    Compute total energy for a full path (list of node IDs).

    Returns:
        total_wh   : total Wh consumed
        total_kwh  : total kWh consumed
        total_soc  : total SoC fraction consumed
        edge_breakdown : list of (u, v, wh) per edge
    """
    total_wh      = 0.0
    edge_breakdown = []

    for i in range(len(path) - 1):
        u = path[i]
        v = path[i + 1]

        # Get edge data (take first edge if parallel edges exist)
        edge_data = G[u][v]
        k         = list(edge_data.keys())[0]
        data      = edge_data[k]

        length_km      = data.get("length_km", data.get("length", 50) / 1000)
        speed_kmh      = data.get("speed", 30.0)
        elevation_gain = data.get("elevation_gain", 0.0)
        elevation_loss = data.get("elevation_loss", 0.0)

        wh, _, _ = compute_edge_energy(
            length_km, speed_kmh, elevation_gain, elevation_loss
        )

        total_wh += wh
        edge_breakdown.append((u, v, wh))

    total_kwh = total_wh / 1000.0
    total_soc = total_kwh / BATTERY_CAPACITY_KWH

    return total_wh, total_kwh, total_soc, edge_breakdown


if __name__ == "__main__":
    # Quick sanity check
    wh, kwh, soc = compute_edge_energy(
        length_km=1.0,
        speed_kmh=40.0,
        elevation_gain=5.0,
        elevation_loss=0.0
    )
    print(f"1km at 40km/h, +5m elevation:")
    print(f"  Energy : {wh:.2f} Wh  |  {kwh:.4f} kWh")
    print(f"  SoC used: {soc*100:.3f}%")