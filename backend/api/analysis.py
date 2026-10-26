from __future__ import annotations

from typing import Any

from flask import Blueprint

from backend.context import workspace_service
from backend.http import ApiError, json_response, ndjson_response, parse_body
from backend.schemas import (
    LandscapeEvaluateRequest,
    LandscapeScenarioEvaluateRequest,
    RegenerationAnalyzeRequest,
)

analysis_api = Blueprint("analysis_api", __name__)


def _evaluate_landscape(payload: LandscapeEvaluateRequest, **extra: Any) -> dict[str, Any]:
    return workspace_service().evaluate_landscape(
        block_ids=payload.block_ids,
        block_actions=payload.block_actions,
        action=payload.action,
        neighborhood_m=payload.neighborhood_m,
        cell_size_m=payload.cell_size_m,
        connectivity=payload.connectivity,
        limit=payload.limit,
        **extra,
    )


@analysis_api.post("/regeneration/analyze")
def run_regeneration_analysis():
    payload = parse_body(RegenerationAnalyzeRequest)
    try:
        result = workspace_service().run_regeneration_analysis(
            inefficiency_threshold=payload.inefficiency_threshold,
            potential_threshold=payload.potential_threshold,
        )
    except ValueError as exc:
        raise ApiError(422, str(exc)) from exc
    return json_response(result)


@analysis_api.get("/landscape/boundary/geojson")
def get_landscape_boundary_geojson():
    try:
        result = workspace_service().landscape_boundary_geojson()
    except ValueError as exc:
        raise ApiError(404, str(exc)) from exc
    return json_response(result)


@analysis_api.post("/landscape/evaluate")
def evaluate_landscape():
    payload = parse_body(LandscapeEvaluateRequest)
    try:
        result = _evaluate_landscape(payload)
    except ValueError as exc:
        raise ApiError(409, str(exc)) from exc
    return json_response(result)


@analysis_api.post("/landscape/evaluate/stream")
def stream_landscape_evaluation():
    payload = parse_body(LandscapeEvaluateRequest)

    def produce(publish):
        result = _evaluate_landscape(
            payload,
            progress_callback=lambda progress: publish({"type": "progress", "progress": progress}),
        )
        publish({"type": "result", "result": result})

    return ndjson_response(produce, error_prefix="边界形态评价失败")


@analysis_api.post("/landscape/scenario/evaluate")
def evaluate_landscape_scenario():
    payload = parse_body(LandscapeScenarioEvaluateRequest)
    try:
        result = workspace_service().evaluate_landscape_scenario(
            block_ids=payload.block_ids,
            action=payload.action,
            neighborhood_m=payload.neighborhood_m,
            cell_size_m=payload.cell_size_m,
            connectivity=payload.connectivity,
        )
    except ValueError as exc:
        raise ApiError(409, str(exc)) from exc
    return json_response(result)
