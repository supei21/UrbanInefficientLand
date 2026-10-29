"""GeoJSON presentation adapter for regeneration analysis results."""

from __future__ import annotations

from typing import Any

from pyproj import Transformer

DEFAULT_PROJECTED_CRS = "EPSG:4547"
_TO_WGS84 = Transformer.from_crs(DEFAULT_PROJECTED_CRS, "EPSG:4326", always_xy=True)


def build_regeneration_point_geojson(
    blocks: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    """Build a point layer when the source dataset has attributes but no geometry."""

    decision_by_id = {
        str(item.get("block_id")): item for item in decisions if item.get("block_id") is not None
    }
    features: list[dict[str, Any]] = []
    for block in blocks:
        block_id = str(block.get("block_id") or block.get("object_id") or "")
        coordinates = _wgs84_coordinates(block)
        decision = decision_by_id.get(block_id)
        if coordinates is None or decision is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": block_id,
                "geometry": {"type": "Point", "coordinates": coordinates},
                "properties": {
                    "block_id": block_id,
                    "block_name": block.get("block_name") or block.get("district"),
                    "district": block.get("district"),
                    "area_km2": block.get("area_km2"),
                    "regeneration_scenario": decision.get("regeneration_scenario"),
                    "decision": decision.get("regeneration_scenario"),
                    "priority_level": decision.get("priority_level"),
                    "priority_score": decision.get("priority_score"),
                    "inefficiency_score": decision.get("inefficiency_score"),
                    "inefficiency_level": decision.get("inefficiency_level"),
                    "dominant_problem": decision.get("dominant_problem"),
                    "screening_status": decision.get("screening_status"),
                    "regeneration_potential": decision.get("regeneration_potential"),
                    "potential_level": decision.get("potential_level"),
                    "dev_score": decision.get("dev_score"),
                    "dev_type": decision.get("dev_type"),
                    "scenario_subtype": decision.get("scenario_subtype"),
                    "scenario_reason": decision.get("scenario_reason"),
                    "constraint_reasons": "、".join(decision.get("constraint_reasons") or []),
                    "implementation_timing": decision.get("implementation_timing"),
                    "scenario_positioning": decision.get("scenario_positioning"),
                    "scenario_actions": "、".join(decision.get("scenario_actions") or []),
                    "key_evidence": "；".join(decision.get("key_evidence") or []),
                    "manual_review_required": decision.get("manual_review_required"),
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "geometry_source": "centroid",
            "source_crs": DEFAULT_PROJECTED_CRS,
            "display_crs": "EPSG:4326",
            "total_features": len(features),
        },
    }


def _wgs84_coordinates(block: dict[str, Any]) -> list[float] | None:
    x = _number(block, "lng", "longitude", "x", "centroid_x")
    y = _number(block, "lat", "latitude", "y", "centroid_y")
    if x is None or y is None:
        return None
    if -180 <= x <= 180 and -90 <= y <= 90:
        return [x, y]
    longitude, latitude = _TO_WGS84.transform(x, y)
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None
    return [round(longitude, 7), round(latitude, 7)]


def _number(block: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = block.get(name)
        if value in (None, "") or isinstance(value, bool):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None
