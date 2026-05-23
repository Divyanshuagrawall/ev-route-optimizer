# routing/lpastar.py

import heapq
import math
from config import MIN_SOC, BATTERY_CAPACITY_KWH
from routing.energy_model import compute_edge_energy
from routing.astar import haversine, heuristic


class LPAStar:
    """
    Lifelong Planning A* for incremental rerouting.

    When the vehicle's position or SoC changes mid-journey,
    LPA* reuses previous search results and only re-explores
    affected parts of the graph — much faster than full A* restart.
    """

    def __init__(self, G, source, target, start_soc, charging_nodes=None):
        self.G               = G
        self.target          = target
        self.charging_nodes  = charging_nodes or set()
        self.start_soc       = start_soc

        # g  : best known cost from source to node
        # rhs: one-step lookahead cost (more consistent than g)
        self.g   = {}
        self.rhs = {}

        # Priority queue
        self.heap = []
        self.heap_set = set()

        # Initialize all nodes
        for node in G.nodes:
            self.g[node]   = math.inf
            self.rhs[node] = math.inf

        # Source is locally consistent at cost 0
        self.rhs[source] = 0.0
        self.source      = source
        self.current_soc = start_soc

        h = heuristic(G, source, target)
        heapq.heappush(self.heap, (self._key(source), source))
        self.heap_set.add(source)


    def _key(self, node):
        """Priority key for node — (min(g,rhs)+h, min(g,rhs))."""
        g_rhs = min(self.g[node], self.rhs[node])
        h     = heuristic(self.G, node, self.target)
        return (g_rhs + h, g_rhs)


    def _update_node(self, node):
        """Recompute rhs and update heap."""
        if node != self.source:
            best_rhs = math.inf

            for pred in self.G.predecessors(node):
                edge_data = self.G[pred][node]
                # Works for both DiGraph and MultiDiGraph
                if isinstance(edge_data, dict) and "time_weight" in edge_data:
                    time_w = edge_data.get("time_weight", 60.0)
                elif isinstance(edge_data, dict):
                    k      = list(edge_data.keys())[0]
                    time_w = edge_data[k].get("time_weight", 60.0)
                else:
                    time_w = 60.0

                candidate = self.g.get(pred, math.inf) + time_w
                if candidate < best_rhs:
                    best_rhs = candidate

            self.rhs[node] = best_rhs
        # Update heap
        if node in self.heap_set:
            self.heap_set.discard(node)

        if self.g[node] != self.rhs[node]:
            heapq.heappush(self.heap, (self._key(node), node))
            self.heap_set.add(node)


    def compute_shortest_path(self):
        """Run LPA* until target is consistent."""
        while self.heap:
            key, node = heapq.heappop(self.heap)
            self.heap_set.discard(node)

            if node == self.target:
                if self.g[self.target] == self.rhs[self.target]:
                    break

            if self.g[node] > self.rhs[node]:
                # Locally overconsistent — update
                self.g[node] = self.rhs[node]
                for neighbor in self.G.neighbors(node):
                    self._update_node(neighbor)
            else:
                # Locally underconsistent — reset and requeue
                self.g[node] = math.inf
                self._update_node(node)
                for neighbor in self.G.neighbors(node):
                    self._update_node(neighbor)


    def extract_path(self):
        """
        Trace back path from target to source using g values.
        Returns list of node IDs.
        """
        if self.g[self.target] == math.inf:
            return None

        path = [self.target]
        node = self.target

        while node != self.source:
            best_pred = None
            best_cost = math.inf

            for pred in self.G.predecessors(node):
                edge_data = self.G[pred][node]
                if isinstance(edge_data, dict) and "time_weight" in edge_data:
                    time_w = edge_data.get("time_weight", 60.0)
                elif isinstance(edge_data, dict):
                    k      = list(edge_data.keys())[0]
                    time_w = edge_data[k].get("time_weight", 60.0)
                else:
                    time_w = 60.0

                cost = self.g.get(pred, math.inf) + time_w
                if cost < best_cost:
                    best_cost = cost
                    best_pred = pred

            if best_pred is None:
                return None

            path.append(best_pred)
            node = best_pred

        path.reverse()
        return path


    def reroute(self, new_source, new_soc):
        """
        Called when vehicle position or SoC changes mid-journey.
        Updates source and recomputes only affected nodes.

        Args:
            new_source : current node ID of vehicle
            new_soc    : current SoC fraction

        Returns:
            path       : updated list of node IDs
            total_time : estimated seconds remaining
            total_kwh  : estimated kWh remaining
        """
        print(f"Rerouting from node {new_source} with SoC={new_soc*100:.1f}%")

        # Reset source
        self.g[self.source]   = math.inf
        self.rhs[self.source] = math.inf

        self.source      = new_source
        self.current_soc = new_soc
        self.rhs[new_source] = 0.0

        heapq.heappush(self.heap, (self._key(new_source), new_source))
        self.heap_set.add(new_source)

        # Recompute
        self.compute_shortest_path()
        path = self.extract_path()

        if path is None:
            print("No path found after rerouting.")
            return None, None, None

        # Estimate time and energy
        total_time = self.g[self.target]
        total_kwh  = self._estimate_energy(path, new_soc)

        return path, total_time, total_kwh


    def _estimate_energy(self, path, start_soc):
        """Estimate kWh consumed along a path."""
        total_kwh = 0.0
        soc       = start_soc

        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]

            if not self.G.has_edge(u, v):
                continue

            edge_data = self.G[u][v]

            # Handle both DiGraph and MultiDiGraph
            if isinstance(edge_data, dict) and "time_weight" in edge_data:
                data = edge_data
            elif isinstance(edge_data, dict):
                k    = list(edge_data.keys())[0]
                data = edge_data[k]
            else:
                continue

            length_km      = data.get("length_km", data.get("length", 50) / 1000)
            speed_kmh      = data.get("speed", 30.0)
            elevation_gain = data.get("elevation_gain", 0.0)
            elevation_loss = data.get("elevation_loss", 0.0)

            _, edge_kwh, _ = compute_edge_energy(
                length_km, speed_kmh, elevation_gain, elevation_loss
            )

            total_kwh += edge_kwh

        return total_kwh


if __name__ == "__main__":
    from graph.map_loader import load_graph
    from graph.graph_builder import add_edge_weights

    G      = load_graph()
    G      = add_edge_weights(G)

    source = list(G.nodes)[0]
    target = list(G.nodes)[100]

    lpa = LPAStar(G, source, target, start_soc=0.80)
    lpa.compute_shortest_path()
    path = lpa.extract_path()

    if path:
        print(f"Initial path: {len(path)} nodes")

        # Simulate reroute from node 10 with lower SoC
        mid_node   = path[10] if len(path) > 10 else path[-1]
        new_path, t, e = lpa.reroute(mid_node, new_soc=0.45)

        if new_path:
            print(f"Rerouted path : {len(new_path)} nodes")
            print(f"Time remaining: {t/60:.1f} min")
            print(f"Energy remaining: {e:.3f} kWh")
    else:
        print("No initial path found.")