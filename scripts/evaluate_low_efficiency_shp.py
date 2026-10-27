"""Evaluate a local block Shapefile ZIP and export standalone SHP layers.

This script does not use the web workspace or its upload/analysis endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import geopandas as gpd
from shapely.strtree import STRtree

from tianshu_core.low_efficiency import DIMENSION_WEIGHTS, evaluate_low_efficiency
from tianshu_core.spatial import read_shapefile_zip_path

FIELD_NOTES = {
    "SRC_ECO": "输入 SHP 原有 eco_ratio 字段，为避免 DBF 字段名大小写冲突而改名",
    "LE_SCORE": "六维综合低效得分，越高表示越低效",
    "LE_LEVEL": "高度低效、明显低效、疑似低效或一般",
    "LE_STATUS": "候选筛选与复核状态",
    "LE_PROB": "六维中得分最高的主导问题",
    "LE_SCENE": "依据六维问题和约束建议的更新场景",
    "CLUSTER": "候选地块按 300 米邻近规则形成的空间簇",
    "CLU_SIZE": "空间簇内候选地块数",
    "LAND_LOW": "土地利用不足得分",
    "VITAL_LOW": "城市活力不足得分",
    "FUNC_MIS": "功能结构失配得分",
    "SERV_GAP": "公共服务短板得分",
    "TRANS_LOW": "交通可达性不足得分",
    "SPACE_Q": "空间品质问题得分",
    "CURR_BLT": "2026 年建设用地比例（Bulit_Area）",
    "PREV_BLT": "2021 年建设用地比例（原始 Bulit_pro2）",
    "BLT_CHG": "2026 年比例减 2021 年比例",
    "BND_RATIO": "城镇开发边界重叠比例",
    "ECO_RATIO": "生态保护红线重叠比例",
    "FAR_RATIO": "永久基本农田重叠比例",
    "REV_CONS": "是否需约束复核：Y 或 N",
    "REV_GEOM": "是否需几何复核：Y 或 N",
    "EVIDENCE": "得分最高的三个低效维度及其得分",
    "COVERAGE": "九项数值指标的数据覆盖率",
    "REVIEW": "是否需要人工复核：Y 或 N",
}


def _numeric(block: dict, name: str) -> float | None:
    value = block.get(name)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _review_flags(block: dict) -> tuple[bool, bool]:
    ecological = _numeric(block, "ecological_ratio") or 0.0
    farmland = _numeric(block, "farmland_ratio") or 0.0
    area = _numeric(block, "area_km2")
    return ecological > 0.01 or farmland > 0.01, area is not None and (area < 0.005 or area > 3.0)


def _scenario(block: dict, dimensions: dict[str, float]) -> str:
    constraint_review, _ = _review_flags(block)
    if constraint_review:
        return "生态修复或约束储备"
    industry = _numeric(block, "poi_industry") or 0.0
    logistics = _numeric(block, "poi_logistics") or 0.0
    poi_total = _numeric(block, "poi_total") or 0.0
    industry_share = (industry + logistics) / poi_total if poi_total > 0 else 0.0
    if industry_share >= 0.35 and max(dimensions["土地利用不足"], dimensions["城市活力不足"]) >= 60:
        return "产业活化"
    if dimensions["功能结构失配"] >= 65:
        return "功能混合"
    if dimensions["公共服务短板"] >= 65:
        return "公共空间与服务提升"
    if dimensions["交通可达性不足"] >= 65:
        return "慢行与交通连接改善"
    return "综合提质"


def _clusters(
    original: gpd.GeoDataFrame, blocks: list[dict], candidates: list[dict]
) -> dict[str, tuple[str, int]]:
    if not candidates:
        return {}
    if not original.crs.is_projected:
        raise ValueError("300 米聚类要求输入 SHP 使用米制投影坐标系")
    ids = [str(blocks[item["source_index"]]["block_id"]) for item in candidates]
    geometries = [original.geometry.iloc[item["source_index"]] for item in candidates]
    tree = STRtree(geometries)
    parent = list(range(len(ids)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for index, geometry in enumerate(geometries):
        for match in tree.query(geometry.buffer(300)):
            other = int(match)
            if other >= index:
                continue
            if geometry.distance(geometries[other]) <= 300:
                parent[find(other)] = find(index)

    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(ids)):
        components[find(index)].append(index)
    ordered = sorted(
        components.values(), key=lambda group: (-len(group), min(ids[i] for i in group))
    )
    return {
        ids[index]: (f"C{cluster_number:03d}", len(group))
        for cluster_number, group in enumerate(ordered, start=1)
        for index in group
    }


def _export_layer(
    raw: gpd.GeoDataFrame,
    blocks: list[dict],
    results: list[dict],
    clusters: dict[str, tuple[str, int]],
    path: Path,
) -> None:
    indices = [item["source_index"] for item in results]
    frame = raw.iloc[indices].reset_index(drop=True).copy()
    dimensions = [item["inefficiency_dimensions"] for item in results]
    source = [blocks[index] for index in indices]
    frame["LE_SCORE"] = [item["inefficiency_score"] for item in results]
    frame["LE_LEVEL"] = [item["inefficiency_level"] for item in results]
    frame["LE_STATUS"] = [item["screening_status"] for item in results]
    frame["LE_PROB"] = [item["dominant_problem"] for item in results]
    frame["LE_SCENE"] = [
        _scenario(block, scores) for block, scores in zip(source, dimensions, strict=True)
    ]
    frame["CLUSTER"] = [clusters.get(str(block["block_id"]), (None, 0))[0] for block in source]
    frame["CLU_SIZE"] = [clusters.get(str(block["block_id"]), (None, 0))[1] for block in source]
    for field, label in (
        ("LAND_LOW", "土地利用不足"),
        ("VITAL_LOW", "城市活力不足"),
        ("FUNC_MIS", "功能结构失配"),
        ("SERV_GAP", "公共服务短板"),
        ("TRANS_LOW", "交通可达性不足"),
        ("SPACE_Q", "空间品质问题"),
    ):
        frame[field] = [row[label] for row in dimensions]
    frame["CURR_BLT"] = [_numeric(block, "Bulit_Area") for block in source]
    frame["PREV_BLT"] = [_numeric(block, "construction_ratio") for block in source]
    frame["BLT_CHG"] = [
        round(current - previous, 6) if current is not None and previous is not None else None
        for block in source
        for current, previous in [
            (_numeric(block, "Bulit_Area"), _numeric(block, "construction_ratio"))
        ]
    ]
    frame["BND_RATIO"] = [_numeric(block, "boundary_overlap_ratio") for block in source]
    frame["ECO_RATIO"] = [_numeric(block, "ecological_ratio") for block in source]
    frame["FAR_RATIO"] = [_numeric(block, "farmland_ratio") for block in source]
    review_flags = [_review_flags(block) for block in source]
    frame["REV_CONS"] = ["Y" if flags[0] else "N" for flags in review_flags]
    frame["REV_GEOM"] = ["Y" if flags[1] else "N" for flags in review_flags]
    frame["EVIDENCE"] = [
        "；".join(evidence.replace(" ", "") for evidence in item["key_evidence"])
        for item in results
    ]
    frame["COVERAGE"] = [item["data_coverage"] for item in results]
    frame["REVIEW"] = ["Y" if item["manual_review_required"] else "N" for item in results]
    frame.to_file(path, driver="ESRI Shapefile", engine="pyogrio", encoding="UTF-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError(f"输出目录已存在，请选择新目录：{args.output_dir}")

    dataset = read_shapefile_zip_path(args.source_zip.name, args.source_zip)
    try:
        raw = gpd.read_file(dataset.source_path, engine="pyogrio")
        if list(raw["block_id"].astype(str)) != [
            str(block["block_id"]) for block in dataset.blocks
        ]:
            raise ValueError("原始 SHP 与评分地块顺序不一致")
        raw = raw.rename(columns={"eco_ratio": "SRC_ECO"})
        overlapping = {
            name for name in raw.columns if name != "SRC_ECO" and name.upper() in FIELD_NOTES
        }
        if overlapping:
            raise ValueError(f"原始 SHP 已有结果字段：{sorted(overlapping)}")
        results = evaluate_low_efficiency(dataset.blocks)
        broad = [item for item in results if item["inefficiency_level"] != "一般"]
        clusters = _clusters(dataset.original, dataset.blocks, broad)
        core = [item for item in broad if item["inefficiency_level"] in {"高度低效", "明显低效"}]
        clean = [item for item in broad if not item["manual_review_required"]]
        layers = {
            f"Wuhan_LE_Evaluated_{len(results)}": results,
            f"Wuhan_LE_Broad_{len(broad)}": broad,
            f"Wuhan_LE_Core_{len(core)}": core,
            f"Wuhan_LE_Clean_{len(clean)}": clean,
        }

        args.output_dir.mkdir(parents=True)
        for name, rows in layers.items():
            _export_layer(raw, dataset.blocks, rows, clusters, args.output_dir / f"{name}.shp")

        summary = {
            "source_zip": str(args.source_zip.resolve()),
            "source_sha256": hashlib.sha256(args.source_zip.read_bytes()).hexdigest(),
            "source_crs": dataset.source_crs,
            "source_attribute_count": len(raw.columns) - 1,
            "source_blocks": len(dataset.blocks),
            "boundary_rule": "boundary_overlap_ratio >= 0.5",
            "evaluated_blocks": len(results),
            "outside_boundary_blocks": len(dataset.blocks) - len(results),
            "level_counts": dict(Counter(item["inefficiency_level"] for item in results)),
            "candidate_count": len(broad),
            "manual_review_count": sum(item["manual_review_required"] for item in broad),
            "screening_status_counts": dict(Counter(item["screening_status"] for item in results)),
            "weights": DIMENSION_WEIGHTS,
            "layers": {name: len(rows) for name, rows in layers.items()},
            "fields": FIELD_NOTES,
        }
        (args.output_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (args.output_dir / "README_使用说明.txt").write_text(
            "街区数据六维低效评价（2026-10-27）\n"
            "输入为指定的街区数据.zip；未通过网页系统导入或分析。\n"
            "开发边界重叠比例≥0.5 的街区参与评价，边界外地块不在这些 SHP 中。\n"
            "Evaluated=全部参与评价；Broad=高度+明显+疑似；"
            "Core=高度+明显；Clean=无需人工复核的 Broad 候选。\n"
            "所有图层保留输入 SHP 的原始属性、坐标系和面几何，并补充 EVIDENCE 等评价字段。\n"
            "字段含义详见 summary.json。\n",
            encoding="utf-8",
        )
        archive_path = args.output_dir.with_suffix(".zip")
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(args.output_dir.iterdir()):
                archive.write(path, arcname=path.name)
        print(json.dumps({"output_zip": str(archive_path), **summary}, ensure_ascii=False))
    finally:
        dataset.close()


if __name__ == "__main__":
    main()
