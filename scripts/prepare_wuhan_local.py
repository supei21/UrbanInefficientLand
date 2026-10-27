"""Prepare local Wuhan blocks from the original ArcGIS data and reviewed overlay.

The source files are read only. The output is ignored by Git and contains input
indicators and spatial overlap ratios, never precomputed low-efficiency scores.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "input" / "Wuhan_block_llm.json"


def _geometry_area_km2(feature: dict) -> float:
    polygons = []
    for ring in feature["geometry"]["rings"]:
        polygon = Polygon(ring)
        if not polygon.is_valid:
            polygon = make_valid(polygon)
        if polygon.geom_type == "Polygon":
            polygons.append(polygon)
        elif polygon.geom_type == "MultiPolygon":
            polygons.extend(polygon.geoms)
    geometry = unary_union(polygons)
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    return geometry.area / 1_000_000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Original 6721-block ArcGIS FeatureSet JSON")
    parser.add_argument(
        "reviewed", type=Path, help="Corrected trial low_efficiency_trial_data.json"
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8-sig"))
    reviewed = json.loads(args.reviewed.read_text(encoding="utf-8-sig"))
    inside = {str(row["block_id"]): row for row in reviewed["inside_records"]}
    reference = source.get("spatialReference") or {}
    wkid = reference.get("latestWkid") or reference.get("wkid")
    if not wkid:
        raise ValueError("Source ArcGIS data has no spatialReference.wkid")
    to_wgs84 = Transformer.from_crs(f"EPSG:{int(wkid)}", "EPSG:4326", always_xy=True)

    blocks = []
    for feature in source["features"]:
        attributes = dict(feature["attributes"])
        row = inside.get(str(attributes.get("block_id")))
        if row is None:
            continue
        for field in (
            "boundary_overlap_ratio",
            "ecological_overlap_ratio",
            "farmland_overlap_ratio",
        ):
            attributes[field] = row[field]
        attributes["geometry_area_km2"] = _geometry_area_km2(feature)
        attributes["inside_boundary"] = True
        attributes["district"] = row.get("name")
        x, y = attributes.get("centroid_x"), attributes.get("centroid_y")
        if x is not None and y is not None:
            attributes["lng"], attributes["lat"] = to_wgs84.transform(float(x), float(y))
        blocks.append(attributes)

    if len(blocks) != len(inside):
        raise ValueError(f"Only matched {len(blocks)} of {len(inside)} reviewed blocks")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"blocks": blocks}, ensure_ascii=False), encoding="utf-8")
    print(f"Prepared {len(blocks)} reviewed Wuhan blocks: {args.output}")


if __name__ == "__main__":
    main()
