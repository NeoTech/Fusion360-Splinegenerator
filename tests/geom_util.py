"""Shared geometry validation helpers for the smoke tests."""

from __future__ import annotations

from typing import List, Tuple

Point = Tuple[float, float]


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return (
        min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
        and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
    )


def segments_intersect(p1, p2, p3, p4) -> bool:
    """True if segment p1-p2 properly intersects p3-p4 (excluding shared ends)."""
    d1 = _orient(p3, p4, p1)
    d2 = _orient(p3, p4, p2)
    d3 = _orient(p1, p2, p3)
    d4 = _orient(p1, p2, p4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True
    if d1 == 0 and _on_segment(p3, p4, p1):
        return True
    if d2 == 0 and _on_segment(p3, p4, p2):
        return True
    if d3 == 0 and _on_segment(p1, p2, p3):
        return True
    if d4 == 0 and _on_segment(p1, p2, p4):
        return True
    return False


def is_simple_polygon(points: List[Point]) -> bool:
    """Check a closed polygon has no self-intersections between non-adjacent
    edges.  ``points`` are the vertices in order; the closing edge is implied."""
    n = len(points)
    if n < 3:
        return False
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            # skip adjacent (they legitimately share a vertex)
            if j == i or j == (i + 1) % n or i == (j + 1) % n:
                continue
            a1, a2 = edges[i]
            b1, b2 = edges[j]
            if segments_intersect(a1, a2, b1, b2):
                return False
    return True


def is_closed_within(points: List[Point], tol: float = 1e-6) -> bool:
    """True if the first and last points coincide (an explicitly closed loop)."""
    if not points:
        return False
    return abs(points[0][0] - points[-1][0]) < tol and abs(
        points[0][1] - points[-1][1]
    ) < tol


def max_radius(points: List[Point]) -> float:
    return max((x * x + y * y) ** 0.5 for (x, y) in points)


def min_radius(points: List[Point]) -> float:
    return min((x * x + y * y) ** 0.5 for (x, y) in points)
