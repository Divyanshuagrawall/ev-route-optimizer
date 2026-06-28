# routing/lpastar.py

import heapq
import math
from config import BATTERY_CAPACITY_KWH
from routing.energy_model import compute_edge_energy
from routing.astar import heuristic


class LPAStar:
    """
    Lifelong Planning A* for incremental rerouting.

    Supports two triggers:
      1. Vehicle position / SoC change  → reroute()
      2. Edge closure (road blocked)    → close_edge()
    """

    def __init__(self, G, source, target, start_soc, charging_nodes=None):
        self.G              = G
        self.target         = target
        self.charging_nodes = charging_nodes or set()
        self.start_soc      = start_soc
        self.source         = source
        self.current_soc    = start_soc

        # closed_edges: set of (u, v) tuples with infinite weight
        self.closed_edges   = set()

        self.g   = {}
        self.rhs = {}
        self.heap     = []
        self.heap_set = set()

        for node in G.nodes:
            self.g[node]   = math.inf
            self.rhs[node] = math.inf

        self.rhs[source] = 0.0
        h = heuristic(G, source, target)
        heapq.heappush(self.heap, (self._key(source), source))
        self.heap_set.add(source)

    # ── Internal helpers ──────────────────────────────────────────────

    def _key(self, node):
        g_rhs = min(self.g[node], self.rhs[node])
        h     = heuristic(self.G, node, self.target)
        return (g_rhs + h, g_rhs)

    def _edge_weight(self, u, v):
        """Return time_weight for edge (u,v), or inf if closed."""
        if (u, v) in self.closed_edges:
            return math.inf
        edge_data = self.G[u][v]
        if isinstance(edge_data, dict) and "time_weight" in edge_data:
            return edge_data.get("time_weight", 60.0)
        elif isinstance(edge_data, dict):
            k = list(edge_data.keys())[0]
            return edge_data[k].get("time_weight", 60.0)
        return 60.0

    def _update_node(self, node):
        """Recompute rhs and update heap."""
        if node != self.source:
            best_rhs = math.inf
            for pred in self.G.predecessors(node):
                w         = self._edge_weight(pred, node)
                candidate = self.g.get(pred, math.inf) + w
                if candidate < best_rhs:
                    best_rhs = candidate
            self.rhs[node] = best_rhs

        self.heap_set.discard(node)
        if self.g[node] != self.rhs[node]:
            heapq.heappush(self.heap, (self._key(node), node))
            self.heap_set.add(node)

    # ── Core search ───────────────────────────────────────────────────

    def compute_shortest_path(self):
        """Run LPA* until target is consistent."""
        while self.heap:
            key, node = heapq.heappop(self.heap)
            self.heap_set.discard(node)

            if node == self.target:
                if self.g[self.target] == self.rhs[self.target]:
                    break

            if self.g[node] > self.rhs[node]:
                self.g[node] = self.rhs[node]
                for neighbor in self.G.neighbors(node):
                    self._update_node(neighbor)
            else:
                self.g[node] = math.inf
                self._update_node(node)
                for neighbor in self.G.neighbors(node):
                    self._update_node(neighbor)

    def extract_path(self):
        """Trace back path from target to source using g values."""
        if self.g.get(self.target, math.inf) == math.inf:
            return None

        path = [self.target]
        node = self.target

        while node != self.source:
            best_pred = None
            best_cost = math.inf

            for pred in self.G.predecessors(node):
                w    = self._edge_weight(pred, node)
                cost = self.g.get(pred, math.inf) + w
                if cost < best_cost:
                    best_cost = cost
                    best_pred = pred

            if best_pred is None:
                return None

            path.append(best_pred)
            node = best_pred

        path.reverse()
        return path

    # ── Public triggers ───────────────────────────────────────────────

    def close_edge(self, u, v):
        """
        Mark edge (u, v) as closed (infinite weight) and
        recompute only the affected portion of the graph.
        This is the core LPA* use case — incremental update.

        Returns: (path, total_time, total_kwh) or (None, None, None)
        """
        print(f"  LPA*: closing edge ({u} → {v})")
        self.closed_edges.add((u, v))

        # Only v and its successors are affected — update them
        self._update_node(v)
        for neighbor in self.G.neighbors(v):
            self._update_node(neighbor)

        self.compute_shortest_path()
        path = self.extract_path()

        if path is None:
            print("  LPA*: no path found after edge closure.")
            return None, None, None

        total_time = self.g.get(self.target, math.inf)
        total_kwh  = self._estimate_energy(path, self.current_soc)
        return path, total_time, total_kwh

    def reroute(self, new_source, new_soc):
        """
        Called when vehicle position or SoC changes mid-journey.
        Updates source and recomputes only affected nodes.
        """
        print(f"  LPA*: rerouting from node {new_source}, SoC={new_soc*100:.1f}%")

        self.g[self.source]   = math.inf
        self.rhs[self.source] = math.inf

        self.source      = new_source
        self.current_soc = new_soc
        self.rhs[new_source] = 0.0

        heapq.heappush(self.heap, (self._key(new_source), new_source))
        self.heap_set.add(new_source)

        self.compute_shortest_path()
        path = self.extract_path()

        if path is None:
            return None, None, None

        total_time = self.g.get(self.target, math.inf)
        total_kwh  = self._estimate_energy(path, new_soc)
        return path, total_time, total_kwh

    def _estimate_energy(self, path, start_soc):
        total_kwh = 0.0
        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]
            if not self.G.has_edge(u, v):
                continue
            edge_data = self.G[u][v]
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