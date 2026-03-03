"""
A* Pathfinding on a Grid Map
─────────────────────────────
Generates optimised navigation paths through the store floor plan.
Supports multi-product route optimisation (nearest-neighbour TSP heuristic).
"""
import heapq
import math
from typing import Optional
from ..core.config import STORE_WIDTH, STORE_HEIGHT, GRID_RESOLUTION

# ── Grid setup ──
COLS = int(STORE_WIDTH / GRID_RESOLUTION)
ROWS = int(STORE_HEIGHT / GRID_RESOLUTION)

# Obstacle grid: 0 = walkable, 1 = blocked (shelves / walls)
# Initialised as fully walkable – shelves are registered dynamically
_obstacle_grid: list[list[int]] = [[0] * COLS for _ in range(ROWS)]


def world_to_grid(x: float, y: float) -> tuple[int, int]:
    col = max(0, min(COLS - 1, int(x / GRID_RESOLUTION)))
    row = max(0, min(ROWS - 1, int(y / GRID_RESOLUTION)))
    return row, col


def grid_to_world(row: int, col: int) -> tuple[float, float]:
    return col * GRID_RESOLUTION + GRID_RESOLUTION / 2, \
           row * GRID_RESOLUTION + GRID_RESOLUTION / 2


def register_obstacle(x: float, y: float, w: float = 1.0, h: float = 1.0):
    """Mark shelf footprint as obstacles on the grid (with margin)."""
    margin = GRID_RESOLUTION
    x0, y0 = world_to_grid(x - w / 2 - margin, y - h / 2 - margin)
    x1, y1 = world_to_grid(x + w / 2 + margin, y + h / 2 + margin)
    for r in range(min(x0, x1), max(x0, x1) + 1):
        for c in range(min(y0, y1), max(y0, y1) + 1):
            if 0 <= r < ROWS and 0 <= c < COLS:
                _obstacle_grid[r][c] = 1


def _heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _neighbors(r: int, c: int):
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (-1, 1), (1, -1), (1, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < ROWS and 0 <= nc < COLS and _obstacle_grid[nr][nc] == 0:
            yield nr, nc


def astar(start_xy: tuple[float, float],
          goal_xy: tuple[float, float]) -> Optional[list[tuple[float, float]]]:
    """
    A* search returning a list of (x, y) world-coordinate waypoints.
    Returns None if no path exists.
    """
    sr, sc = world_to_grid(*start_xy)
    gr, gc = world_to_grid(*goal_xy)

    # Ensure start/goal are walkable (force them open)
    _obstacle_grid[sr][sc] = 0
    _obstacle_grid[gr][gc] = 0

    open_set: list[tuple[float, int, int]] = []
    heapq.heappush(open_set, (0.0, sr, sc))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {(sr, sc): 0.0}

    while open_set:
        _, cr, cc = heapq.heappop(open_set)
        if (cr, cc) == (gr, gc):
            # Reconstruct path
            path_grid = [(gr, gc)]
            cur = (gr, gc)
            while cur in came_from:
                cur = came_from[cur]
                path_grid.append(cur)
            path_grid.reverse()
            # Simplify: convert to world & skip collinear points
            return _simplify([grid_to_world(r, c) for r, c in path_grid])

        for nr, nc in _neighbors(cr, cc):
            move_cost = 1.414 if (nr != cr and nc != cc) else 1.0
            tentative = g_score[(cr, cc)] + move_cost
            if tentative < g_score.get((nr, nc), float("inf")):
                came_from[(nr, nc)] = (cr, cc)
                g_score[(nr, nc)] = tentative
                f = tentative + _heuristic((nr, nc), (gr, gc))
                heapq.heappush(open_set, (f, nr, nc))

    return None  # no path


def _simplify(path: list[tuple[float, float]],
              tolerance: float = 0.3) -> list[tuple[float, float]]:
    """Douglas-Peucker simplification to reduce path points."""
    if len(path) <= 2:
        return path

    # Find the point with the maximum distance from the line start→end
    start, end = path[0], path[-1]
    max_dist = 0.0
    idx = 0
    for i in range(1, len(path) - 1):
        d = _point_line_dist(path[i], start, end)
        if d > max_dist:
            max_dist = d
            idx = i

    if max_dist > tolerance:
        left = _simplify(path[: idx + 1], tolerance)
        right = _simplify(path[idx:], tolerance)
        return left[:-1] + right
    else:
        return [start, end]


def _point_line_dist(p, a, b):
    """Perpendicular distance from point p to line a–b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    proj_x = a[0] + t * dx
    proj_y = a[1] + t * dy
    return math.hypot(p[0] - proj_x, p[1] - proj_y)


def path_distance(path: list[tuple[float, float]]) -> float:
    d = 0.0
    for i in range(1, len(path)):
        d += math.hypot(path[i][0] - path[i - 1][0],
                        path[i][1] - path[i - 1][1])
    return d


def multi_product_route(start: tuple[float, float],
                        targets: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """
    Nearest-neighbour heuristic for multi-product route.
    Returns the concatenated optimal-ish path visiting all targets.
    """
    if not targets:
        return []

    remaining = list(targets)
    full_path: list[tuple[float, float]] = []
    current = start

    while remaining:
        # Pick nearest target
        best_idx = 0
        best_dist = float("inf")
        for i, t in enumerate(remaining):
            d = math.hypot(t[0] - current[0], t[1] - current[1])
            if d < best_dist:
                best_dist = d
                best_idx = i

        target = remaining.pop(best_idx)
        segment = astar(current, target)
        if segment:
            if full_path:
                segment = segment[1:]  # avoid duplicate waypoint
            full_path.extend(segment)
        current = target

    return full_path
