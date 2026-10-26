from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tianshu_core.gis import SHP_FIELD_ALIASES
from tianshu_core.paths import PROJECT_ROOT
from tianshu_core.tools.model_features import (
    build_model_feature_frame,
    load_feature_schema,
)

DEFAULT_MODEL_DIR = PROJECT_ROOT / "models"
DEFAULT_ADJUSTMENT_CLASS_NAMES = ["未调整", "预测调入", "预测调出"]


class TrainedBoundaryModelError(RuntimeError):
    pass


@dataclass(slots=True)
class PredictionBundle:
    blocks: list[dict[str, Any]]
    records: list[dict[str, Any]]
    model_dir: str
    feature_count: int
    missing_features: list[str]
    source: str
    warning: str | None = None
    class_count: int = 1
    class_names: list[str] | None = None
    model_type: str = "binary_development"


class XGBoostJsonPredictor:
    """Minimal XGBoost JSON predictor for binary and multiclass tree models."""

    def __init__(self, model_path: Path, feature_names: list[str]) -> None:
        with Path(model_path).open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        learner = payload["learner"]
        self.feature_names = feature_names
        booster_model = learner["gradient_booster"]["model"]
        self.trees = booster_model["trees"]
        self.compiled_trees = [self._compile_tree(tree) for tree in self.trees]
        self.tree_info = [
            int(value) for value in booster_model.get("tree_info", [0] * len(self.trees))
        ]
        learner_params = learner["learner_model_param"]
        self.num_class = max(1, int(learner_params.get("num_class", "0")))
        self.objective = str(learner.get("objective", {}).get("name", "binary:logistic"))
        base_score = self._parse_base_score(learner_params.get("base_score", "0.5"))
        self.base_margin = base_score if self.num_class > 1 else self._logit(base_score)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        x = frame[self.feature_names].apply(pd.to_numeric, errors="coerce")
        x = x.replace([np.inf, -np.inf], np.nan)
        # XGBoost's DMatrix evaluates numeric features as float32.  Matching that
        # precision is important for values that sit exactly on a learned split.
        values = x.to_numpy(dtype=np.float32)
        if self.num_class > 1:
            margins = np.full((len(values), self.num_class), self.base_margin, dtype=float)
            for tree, group in zip(self.compiled_trees, self.tree_info, strict=True):
                margins[:, group] += self._tree_values(values, tree)
            shifted = margins - margins.max(axis=1, keepdims=True)
            exponentials = np.exp(shifted)
            return exponentials / exponentials.sum(axis=1, keepdims=True)

        margins = np.full(len(values), self.base_margin, dtype=float)
        for tree in self.compiled_trees:
            margins += self._tree_values(values, tree)
        positive = np.empty(len(margins), dtype=float)
        nonnegative = margins >= 0
        positive[nonnegative] = 1 / (1 + np.exp(-margins[nonnegative]))
        exp_values = np.exp(margins[~nonnegative])
        positive[~nonnegative] = exp_values / (1 + exp_values)
        return positive

    @staticmethod
    def _compile_tree(tree: dict[str, Any]) -> dict[str, np.ndarray]:
        return {
            "left_children": np.asarray(tree["left_children"], dtype=np.int32),
            "right_children": np.asarray(tree["right_children"], dtype=np.int32),
            "default_left": np.asarray(tree["default_left"], dtype=bool),
            "split_indices": np.asarray(tree["split_indices"], dtype=np.int32),
            "split_conditions": np.asarray(tree["split_conditions"], dtype=np.float32),
            "base_weights": np.asarray(tree["base_weights"], dtype=float),
        }

    @staticmethod
    def _tree_values(values: np.ndarray, tree: dict[str, np.ndarray]) -> np.ndarray:
        nodes = np.zeros(len(values), dtype=np.int32)
        active = np.ones(len(values), dtype=bool)
        while active.any():
            row_indexes = np.flatnonzero(active)
            current_nodes = nodes[row_indexes]
            left_children = tree["left_children"][current_nodes]
            leaf_mask = left_children == -1
            if leaf_mask.any():
                active[row_indexes[leaf_mask]] = False
            branch_rows = row_indexes[~leaf_mask]
            if not len(branch_rows):
                continue
            branch_nodes = current_nodes[~leaf_mask]
            feature_indexes = tree["split_indices"][branch_nodes]
            feature_values = values[branch_rows, feature_indexes]
            missing = np.isnan(feature_values)
            go_left = np.where(
                missing,
                tree["default_left"][branch_nodes],
                feature_values < tree["split_conditions"][branch_nodes],
            )
            nodes[branch_rows] = np.where(
                go_left,
                tree["left_children"][branch_nodes],
                tree["right_children"][branch_nodes],
            )
        return tree["base_weights"][nodes]

    def _predict_row(self, row: pd.Series) -> float | np.ndarray:
        if self.num_class > 1:
            margins = np.full(self.num_class, self.base_margin, dtype=float)
            for tree, group in zip(self.trees, self.tree_info, strict=True):
                margins[group] += self._tree_value(row, tree)
            return self._softmax(margins)

        margin = self.base_margin
        for tree in self.trees:
            margin += self._tree_value(row, tree)
        return self._sigmoid(margin)

    @staticmethod
    def _tree_value(row: pd.Series, tree: dict[str, Any]) -> float:
        node = 0
        left_children = tree["left_children"]
        right_children = tree["right_children"]
        default_left = tree["default_left"]
        split_indices = tree["split_indices"]
        split_conditions = tree["split_conditions"]
        base_weights = tree["base_weights"]
        while left_children[node] != -1:
            feature_index = int(split_indices[node])
            value = row.iloc[feature_index]
            threshold = np.float32(split_conditions[node])
            if pd.isna(value):
                node = left_children[node] if default_left[node] else right_children[node]
            elif np.float32(value) < threshold:
                node = left_children[node]
            else:
                node = right_children[node]
        return float(base_weights[node])

    @staticmethod
    def _parse_base_score(value: Any) -> float:
        text = str(value).strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1].split(",", 1)[0]
        return float(text)

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        shifted = values - np.max(values)
        exponentials = np.exp(shifted)
        return exponentials / exponentials.sum()

    @staticmethod
    def _logit(value: float) -> float:
        clipped = min(max(value, 1e-12), 1 - 1e-12)
        return math.log(clipped / (1 - clipped))

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1 / (1 + z)
        z = math.exp(value)
        return z / (1 + z)


def resolve_model_dir(config: dict[str, Any]) -> Path:
    configured = (
        os.getenv("TIANSHU_TRAINED_MODEL_DIR")
        or config.get("trained_model", {}).get("model_dir")
        or str(DEFAULT_MODEL_DIR)
    )
    model_dir = Path(configured).expanduser()
    if not model_dir.is_absolute():
        model_dir = PROJECT_ROOT / model_dir
    return model_dir.resolve()


def trained_model_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("trained_model", {}).get("enabled", True))


def load_feature_names(model_dir: Path) -> list[str]:
    path = model_dir / "feature_names.json"
    if not path.exists():
        raise TrainedBoundaryModelError(f"未找到模型特征文件：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_training_metrics(model_dir: Path) -> dict[str, Any]:
    path = model_dir / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_predictor(model_dir: Path) -> tuple[XGBoostJsonPredictor, list[str]]:
    model_path = model_dir / "xgb_boundary.json"
    if not model_path.exists():
        raise TrainedBoundaryModelError(f"未找到XGBoost JSON模型：{model_path}")
    feature_names = load_feature_names(model_dir)
    return XGBoostJsonPredictor(model_path, feature_names), feature_names


def load_dual_predictors(
    model_dir: Path,
) -> tuple[XGBoostJsonPredictor, list[str], XGBoostJsonPredictor, list[str], dict[str, Any]]:
    manifest_path = model_dir / "model_manifest.json"
    if not manifest_path.exists():
        raise TrainedBoundaryModelError(f"未找到双模型清单：{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_type") != "dual_binary_adjustment":
        raise TrainedBoundaryModelError("模型清单不是调入/调出双二分类结构")

    inclusion_features = json.loads(
        (model_dir / manifest.get("inclusion_features", "inclusion_feature_names.json")).read_text(
            encoding="utf-8"
        )
    )
    exclusion_features = json.loads(
        (model_dir / manifest.get("exclusion_features", "exclusion_feature_names.json")).read_text(
            encoding="utf-8"
        )
    )
    inclusion_predictor = XGBoostJsonPredictor(
        model_dir / manifest.get("inclusion_model", "inclusion_xgb.json"),
        inclusion_features,
    )
    exclusion_predictor = XGBoostJsonPredictor(
        model_dir / manifest.get("exclusion_model", "exclusion_xgb.json"),
        exclusion_features,
    )
    return (
        inclusion_predictor,
        inclusion_features,
        exclusion_predictor,
        exclusion_features,
        manifest,
    )


ENGINEERED_FEATURE_SOURCES = {
    "feat_compactness": ["Shape_Area", "Shape_Leng"],
    "feat_poi_service_mix": ["poi_indust", "poi_public", "poi_transp"],
    "feat_transport_support": ["road_densi", "poi_transp"],
    "feat_public_population_support": ["poi_public", "pop_raw_su", "area_km2"],
    "feat_industry_accessibility": ["poi_indust", "road_densi"],
    "feat_built_activity": ["Bulit_prop", "NTL_MEAN"],
    "feat_ecological_open_space": ["Water_prop", "Tree_prop", "Crop_prop", "Range_prop"],
    "feat_terrain_access_pressure": ["dem_relief", "road_densi"],
}


def _positive_log1p(values: pd.Series) -> pd.Series:
    return np.log1p(pd.to_numeric(values, errors="coerce").clip(lower=0).fillna(0.0))


def _build_dual_feature_frames(
    blocks: list[dict[str, Any]],
    inclusion_features: list[str],
    exclusion_features: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    requested = list(dict.fromkeys(inclusion_features + exclusion_features))
    raw_features = [name for name in requested if name not in ENGINEERED_FEATURE_SOURCES]
    for feature in requested:
        raw_features.extend(ENGINEERED_FEATURE_SOURCES.get(feature, []))
    raw_features = list(dict.fromkeys(raw_features))
    frame, raw_missing = build_model_feature_frame(blocks, raw_features, None)

    if "feat_compactness" in requested:
        denominator = frame["Shape_Leng"].pow(2).replace(0, np.nan)
        frame["feat_compactness"] = (4.0 * math.pi * frame["Shape_Area"] / denominator).clip(0, 1)
    if "feat_poi_service_mix" in requested:
        frame["feat_poi_service_mix"] = _positive_log1p(
            frame[["poi_indust", "poi_public", "poi_transp"]].fillna(0).sum(axis=1)
        )
    if "feat_transport_support" in requested:
        frame["feat_transport_support"] = _positive_log1p(frame["road_densi"]) * _positive_log1p(
            frame["poi_transp"]
        )
    if "feat_public_population_support" in requested:
        population_density = frame["pop_raw_su"] / frame["area_km2"].replace(0, np.nan)
        frame["feat_public_population_support"] = _positive_log1p(
            frame["poi_public"]
        ) * _positive_log1p(population_density)
    if "feat_industry_accessibility" in requested:
        frame["feat_industry_accessibility"] = _positive_log1p(
            frame["poi_indust"]
        ) * _positive_log1p(frame["road_densi"])
    if "feat_built_activity" in requested:
        frame["feat_built_activity"] = frame["Bulit_prop"].clip(lower=0).fillna(
            0
        ) * _positive_log1p(frame["NTL_MEAN"])
    if "feat_ecological_open_space" in requested:
        frame["feat_ecological_open_space"] = (
            frame[["Water_prop", "Tree_prop", "Crop_prop", "Range_prop"]]
            .clip(lower=0)
            .fillna(0)
            .sum(axis=1)
        )
    if "feat_terrain_access_pressure" in requested:
        frame["feat_terrain_access_pressure"] = frame["dem_relief"].clip(lower=0) / (
            1.0 + frame["road_densi"].clip(lower=0).fillna(0)
        )

    missing = set(name for name in raw_missing if name in requested)
    for engineered, sources in ENGINEERED_FEATURE_SOURCES.items():
        if engineered in requested and any(source in raw_missing for source in sources):
            missing.add(engineered)
    frame = frame.replace([np.inf, -np.inf], np.nan)
    return frame[inclusion_features], frame[exclusion_features], sorted(missing)


@lru_cache(maxsize=4)
def load_shap_explanations(
    model_dir: Path,
) -> tuple[dict[str, str], dict[str, dict[str, list[str]]], list[str], list[str]]:
    """Load precomputed global and per-block SHAP drivers when available."""
    feature_labels: dict[str, str] = {}
    inclusion_global: list[tuple[float, str]] = []
    exclusion_global: list[tuple[float, str]] = []
    contribution_path = model_dir / "shap_feature_contributions.csv"
    if contribution_path.exists():
        with contribution_path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                feature = str(row.get("feature") or "").strip()
                if not feature:
                    continue
                label = str(row.get("feature_label_cn") or feature).strip()
                feature_labels[feature] = label
                try:
                    inclusion_value = float(row.get("actual_inclusion_support_mean") or 0)
                    exclusion_value = float(row.get("actual_exclusion_support_mean") or 0)
                except (TypeError, ValueError):
                    continue
                inclusion_global.append((inclusion_value, label))
                exclusion_global.append((exclusion_value, label))

    per_block: dict[str, dict[str, list[str]]] = {}
    block_path = model_dir / "shap_by_block.csv"
    if block_path.exists():
        with block_path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                block_id = str(row.get("block_id") or "").strip()
                if not block_id:
                    continue
                per_block[block_id] = {
                    "inclusion": _driver_labels(
                        row.get("top_inclusion_supporting_features"), feature_labels
                    ),
                    "exclusion": _driver_labels(
                        row.get("top_exclusion_supporting_features"), feature_labels
                    ),
                }
    inclusion_top = [label for _, label in sorted(inclusion_global, reverse=True)[:5]]
    exclusion_top = [label for _, label in sorted(exclusion_global, reverse=True)[:5]]
    return feature_labels, per_block, inclusion_top, exclusion_top


def _driver_labels(value: Any, feature_labels: dict[str, str]) -> list[str]:
    features = [item.strip() for item in str(value or "").split(";") if item.strip()]
    return [feature_labels.get(feature, feature) for feature in features[:5]]


def enrich_blocks_with_model_predictions(
    blocks: list[dict[str, Any]],
    config: dict[str, Any],
) -> PredictionBundle:
    # Screening profiles must execute the adjustment model even when an upload
    # carries a legacy development score. Legacy profiles retain their behavior.
    prefer_model = bool(config.get("trained_model", {}).get("prefer_adjustment_model", False))
    if not prefer_model:
        potential_bundle = _bundle_from_development_potential(blocks)
        if potential_bundle is not None:
            return potential_bundle

    if not trained_model_enabled(config):
        return PredictionBundle(
            blocks=[dict(item) for item in blocks],
            records=[],
            model_dir="",
            feature_count=0,
            missing_features=[],
            source="proxy",
            warning="训练模型工具未启用，沿用工作流内置代理概率。",
        )

    model_dir = resolve_model_dir(config)
    manifest_path = model_dir / "model_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("model_type") == "dual_binary_adjustment":
            return _dual_binary_prediction_bundle(blocks, model_dir, config)

    predictor, feature_names = load_predictor(model_dir)
    feature_schema = load_feature_schema(model_dir)
    frame, missing_features = build_model_feature_frame(
        blocks,
        feature_names,
        feature_schema,
    )
    available_features = [feature for feature in feature_names if frame[feature].notna().any()]
    min_coverage = float(config.get("trained_model", {}).get("min_feature_coverage", 0.5))
    coverage = len(available_features) / max(len(feature_names), 1)
    if coverage < min_coverage:
        raise TrainedBoundaryModelError(
            f"模型特征覆盖率不足（{coverage:.0%}，要求不低于{min_coverage:.0%}）"
        )
    probabilities = predictor.predict_proba(frame)

    if predictor.num_class > 1:
        return _multiclass_prediction_bundle(
            blocks,
            probabilities,
            predictor,
            feature_names,
            missing_features,
            model_dir,
            config,
        )

    enriched: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for block, probability in zip(blocks, probabilities, strict=True):
        score = round(float(probability) * 100, 2)
        updated = dict(block)
        updated["development_probability"] = score
        updated["model_probability"] = round(float(probability), 6)
        updated["model_source"] = "xgb_boundary_json"
        enriched.append(updated)
        records.append(
            {
                "block_id": str(updated.get("block_id")),
                "block_name": updated.get("block_name"),
                "development_probability": score,
                "model_probability": round(float(probability), 6),
            }
        )

    records.sort(key=lambda item: (-float(item["development_probability"]), str(item["block_id"])))
    return PredictionBundle(
        blocks=enriched,
        records=records,
        model_dir=str(model_dir),
        feature_count=len(feature_names),
        missing_features=missing_features,
        source="xgb_boundary_json",
    )


def _dual_binary_prediction_bundle(
    blocks: list[dict[str, Any]],
    model_dir: Path,
    config: dict[str, Any],
) -> PredictionBundle:
    (
        inclusion_predictor,
        inclusion_features,
        exclusion_predictor,
        exclusion_features,
        manifest,
    ) = load_dual_predictors(model_dir)
    inclusion_frame, exclusion_frame, missing_features = _build_dual_feature_frames(
        blocks,
        inclusion_features,
        exclusion_features,
    )
    available = set(inclusion_features + exclusion_features) - set(missing_features)
    union_features = list(dict.fromkeys(inclusion_features + exclusion_features))
    coverage = len(available) / max(len(union_features), 1)
    min_coverage = float(config.get("trained_model", {}).get("min_feature_coverage", 0.5))
    if coverage < min_coverage:
        raise TrainedBoundaryModelError(
            f"双模型特征覆盖率不足（{coverage:.0%}，要求不低于{min_coverage:.0%}）"
        )

    inclusion_probability = inclusion_predictor.predict_proba(inclusion_frame)
    exclusion_probability = exclusion_predictor.predict_proba(exclusion_frame)
    thresholds = manifest.get("thresholds") or {}
    inclusion_threshold = float(thresholds.get("inclusion", 0.5))
    exclusion_threshold = float(thresholds.get("exclusion", 0.5))
    class_names = [
        str(value) for value in manifest.get("class_names", DEFAULT_ADJUSTMENT_CLASS_NAMES)
    ]
    if len(class_names) != 3:
        class_names = list(DEFAULT_ADJUSTMENT_CLASS_NAMES)

    _, per_block, global_inclusion, global_exclusion = load_shap_explanations(model_dir)
    enriched: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for block, prob_in, prob_out in zip(
        blocks,
        inclusion_probability,
        exclusion_probability,
        strict=True,
    ):
        prob_in = float(prob_in)
        prob_out = float(prob_out)
        inside_boundary = block.get("inside_boundary")
        if inside_boundary is True:
            predicted_class = 2 if prob_out >= exclusion_threshold else 0
            no_change_probability = 1.0 - prob_out
        elif inside_boundary is False:
            predicted_class = 1 if prob_in >= inclusion_threshold else 0
            no_change_probability = 1.0 - prob_in
        else:
            inclusion_active = prob_in >= inclusion_threshold
            exclusion_active = prob_out >= exclusion_threshold
            if inclusion_active and exclusion_active:
                predicted_class = (
                    1
                    if prob_in / max(inclusion_threshold, 1e-12)
                    >= prob_out / max(exclusion_threshold, 1e-12)
                    else 2
                )
            elif inclusion_active:
                predicted_class = 1
            elif exclusion_active:
                predicted_class = 2
            else:
                predicted_class = 0
            no_change_probability = 1.0 - max(prob_in, prob_out)

        model_confidence = (
            no_change_probability
            if predicted_class == 0
            else prob_in
            if predicted_class == 1
            else prob_out
        )
        block_id = str(block.get("block_id") or "")
        block_shap = per_block.get(block_id, {})
        inclusion_drivers = block_shap.get("inclusion") or global_inclusion
        exclusion_drivers = block_shap.get("exclusion") or global_exclusion
        updated = dict(block)
        updated.update(
            {
                "development_probability": round(prob_in * 100, 2),
                "model_probability": round(prob_in, 6),
                "model_confidence": round(float(model_confidence), 6),
                "model_source": "optimized_dual_xgb_json",
                "adjustment_class": predicted_class,
                "adjustment_label": class_names[predicted_class],
                "prob_no_change": round(max(0.0, no_change_probability), 6),
                "prob_inclusion": round(prob_in, 6),
                "prob_exclusion": round(prob_out, 6),
                "screening_inclusion": prob_in >= inclusion_threshold,
                "screening_exclusion": prob_out >= exclusion_threshold,
                "screening_stage": "model_only_requires_spatial_policy_review",
                "shap_inclusion_drivers": inclusion_drivers,
                "shap_exclusion_drivers": exclusion_drivers,
            }
        )
        enriched.append(updated)
        records.append(
            {
                "block_id": block_id,
                "block_name": updated.get("block_name"),
                "adjustment_class": predicted_class,
                "adjustment_label": class_names[predicted_class],
                "prob_no_change": round(max(0.0, no_change_probability), 6),
                "prob_inclusion": round(prob_in, 6),
                "prob_exclusion": round(prob_out, 6),
                "screening_inclusion": prob_in >= inclusion_threshold,
                "screening_exclusion": prob_out >= exclusion_threshold,
                "screening_stage": "model_only_requires_spatial_policy_review",
                "model_confidence": round(float(model_confidence), 6),
                "development_probability": round(prob_in * 100, 2),
                "shap_inclusion_drivers": inclusion_drivers,
                "shap_exclusion_drivers": exclusion_drivers,
            }
        )
    records.sort(
        key=lambda item: (
            -max(float(item["prob_inclusion"]), float(item["prob_exclusion"])),
            str(item["block_id"]),
        )
    )
    return PredictionBundle(
        blocks=enriched,
        records=records,
        model_dir=str(model_dir),
        feature_count=len(union_features),
        missing_features=missing_features,
        source="optimized_dual_xgb_json",
        class_count=3,
        class_names=class_names,
        model_type="dual_binary_adjustment",
    )


def _multiclass_prediction_bundle(
    blocks: list[dict[str, Any]],
    probabilities: np.ndarray,
    predictor: XGBoostJsonPredictor,
    feature_names: list[str],
    missing_features: list[str],
    model_dir: Path,
    config: dict[str, Any],
) -> PredictionBundle:
    if probabilities.ndim != 2 or probabilities.shape[1] != predictor.num_class:
        raise TrainedBoundaryModelError(f"多分类模型输出形状异常：{probabilities.shape}")
    configured_names = config.get("trained_model", {}).get("class_names")
    class_names = (
        [str(value) for value in configured_names]
        if isinstance(configured_names, list) and len(configured_names) == predictor.num_class
        else DEFAULT_ADJUSTMENT_CLASS_NAMES[: predictor.num_class]
    )
    if len(class_names) != predictor.num_class:
        class_names = [f"类别{index}" for index in range(predictor.num_class)]

    _, per_block, global_inclusion, global_exclusion = load_shap_explanations(model_dir)
    enriched: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for block, row in zip(blocks, probabilities, strict=True):
        predicted_class = int(np.argmax(row))
        block_id = str(block.get("block_id") or "")
        block_shap = per_block.get(block_id, {})
        inclusion_drivers = block_shap.get("inclusion") or global_inclusion
        exclusion_drivers = block_shap.get("exclusion") or global_exclusion
        updated = dict(block)
        updated.update(
            {
                "development_probability": round(float(row[1]) * 100, 2),
                "model_probability": round(float(row[1]), 6),
                "model_confidence": round(float(row[predicted_class]), 6),
                "model_source": "actual_adjustment_xgb_json",
                "adjustment_class": predicted_class,
                "adjustment_label": class_names[predicted_class],
                "prob_no_change": round(float(row[0]), 6),
                "prob_inclusion": round(float(row[1]), 6),
                "prob_exclusion": round(float(row[2]), 6),
                "shap_inclusion_drivers": inclusion_drivers,
                "shap_exclusion_drivers": exclusion_drivers,
            }
        )
        enriched.append(updated)
        records.append(
            {
                "block_id": block_id,
                "block_name": updated.get("block_name"),
                "adjustment_class": predicted_class,
                "adjustment_label": class_names[predicted_class],
                "prob_no_change": round(float(row[0]), 6),
                "prob_inclusion": round(float(row[1]), 6),
                "prob_exclusion": round(float(row[2]), 6),
                "model_confidence": round(float(row[predicted_class]), 6),
                "development_probability": round(float(row[1]) * 100, 2),
                "shap_inclusion_drivers": inclusion_drivers,
                "shap_exclusion_drivers": exclusion_drivers,
            }
        )
    records.sort(
        key=lambda item: (
            -max(float(item["prob_inclusion"]), float(item["prob_exclusion"])),
            str(item["block_id"]),
        )
    )
    return PredictionBundle(
        blocks=enriched,
        records=records,
        model_dir=str(model_dir),
        feature_count=len(feature_names),
        missing_features=missing_features,
        source="actual_adjustment_xgb_json",
        class_count=predictor.num_class,
        class_names=class_names,
        model_type="multiclass_adjustment",
    )


def _bundle_from_development_potential(
    blocks: list[dict[str, Any]],
) -> PredictionBundle | None:
    if not blocks:
        return None
    has_field = [
        block.get("development_potential") is not None or block.get("dev_score") is not None
        for block in blocks
    ]
    if not any(has_field):
        return None
    if not all(has_field):
        raise TrainedBoundaryModelError("综合发展潜力字段不完整，部分地块缺少 dev_score")

    enriched: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    for block in blocks:
        raw_value = block.get("development_potential", block.get("dev_score"))
        try:
            potential = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise TrainedBoundaryModelError("dev_score 必须是 0 到 1 之间的数值") from exc
        if not math.isfinite(potential) or not 0 <= potential <= 1:
            raise TrainedBoundaryModelError(f"dev_score 超出 0 到 1 范围：{raw_value}")

        probability = round(potential * 100, 2)
        updated = dict(block)
        updated["development_potential"] = potential
        updated["development_probability"] = probability
        updated["model_probability"] = round(potential, 6)
        updated["model_source"] = "uploaded_development_potential"
        enriched.append(updated)
        records.append(
            {
                "block_id": str(updated.get("block_id")),
                "block_name": updated.get("block_name"),
                "development_probability": probability,
                "model_probability": round(potential, 6),
            }
        )

    records.sort(key=lambda item: (-float(item["development_probability"]), str(item["block_id"])))
    return PredictionBundle(
        blocks=enriched,
        records=records,
        model_dir="input:dev_score",
        feature_count=1,
        missing_features=[],
        source="uploaded_development_potential",
    )


def model_status(config: dict[str, Any]) -> dict[str, Any]:
    if not trained_model_enabled(config):
        return {"enabled": False, "available": False, "warning": "训练模型工具未启用"}
    model_dir = resolve_model_dir(config)
    try:
        feature_names = load_feature_names(model_dir)
        metrics = load_training_metrics(model_dir)
        feature_schema = load_feature_schema(model_dir)
        _, per_block, inclusion_top, exclusion_top = load_shap_explanations(model_dir)
        manifest_path = model_dir / "model_manifest.json"
        manifest = (
            json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        )
        is_dual = manifest.get("model_type") == "dual_binary_adjustment"
        if is_dual:
            (
                inclusion_predictor,
                inclusion_features,
                exclusion_predictor,
                exclusion_features,
                _,
            ) = load_dual_predictors(model_dir)
            model_available = all(
                (model_dir / name).exists()
                for name in [
                    manifest.get("inclusion_model", "inclusion_xgb.json"),
                    manifest.get("exclusion_model", "exclusion_xgb.json"),
                ]
            )
        else:
            predictor, _ = load_predictor(model_dir)
            model_available = (model_dir / "xgb_boundary.json").exists()
    except Exception as exc:
        return {
            "enabled": True,
            "available": False,
            "model_dir": str(model_dir),
            "warning": str(exc),
        }
    return {
        "enabled": True,
        "available": model_available,
        "model_dir": str(model_dir),
        "feature_count": len(feature_names),
        "feature_schema_version": (feature_schema or {}).get("schema_version", 1),
        "model_type": (
            "dual_binary_adjustment"
            if is_dual
            else "multiclass_adjustment"
            if predictor.num_class > 1
            else "binary_development"
        ),
        "objective": (
            f"{inclusion_predictor.objective} + {exclusion_predictor.objective}"
            if is_dual
            else predictor.objective
        ),
        "class_count": 3 if is_dual else predictor.num_class,
        "class_names": (
            manifest.get("class_names", DEFAULT_ADJUSTMENT_CLASS_NAMES)
            if is_dual
            else config.get("trained_model", {}).get("class_names")
            if predictor.num_class > 1
            else ["非目标", "目标"]
        ),
        "thresholds": manifest.get("thresholds") if is_dual else None,
        "inclusion_feature_count": len(inclusion_features) if is_dual else None,
        "exclusion_feature_count": len(exclusion_features) if is_dual else None,
        "shap_available": bool(inclusion_top or exclusion_top),
        "shap_block_count": len(per_block),
        "shap_inclusion_top": inclusion_top,
        "shap_exclusion_top": exclusion_top,
        "metrics": metrics,
    }


def _build_feature_frame(
    blocks: list[dict[str, Any]],
    feature_names: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    rows = []
    missing_features: set[str] = set()
    for block in blocks:
        row = {}
        lower_map = {str(key).lower(): key for key in block}
        for feature in feature_names:
            value = _lookup_feature(block, lower_map, feature)
            if value is None:
                missing_features.add(feature)
            row[feature] = value
        rows.append(row)
    return pd.DataFrame(rows, columns=feature_names), sorted(missing_features)


def _lookup_feature(block: dict[str, Any], lower_map: dict[str, str], feature: str) -> Any:
    if feature in block:
        return block[feature]
    lowered_key = lower_map.get(feature.lower())
    if lowered_key is not None:
        return block[lowered_key]
    canonical = SHP_FIELD_ALIASES.get(feature)
    if canonical and canonical in block:
        return block[canonical]
    canonical_key = lower_map.get(str(canonical).lower()) if canonical else None
    if canonical_key:
        return block[canonical_key]
    return None
