from __future__ import annotations

import zipfile

from flask import Blueprint, request, send_file

from backend.context import workspace_service
from backend.http import ApiError, integer_query, json_response, ndjson_response, parse_body
from backend.policy_documents import POLICY_REFERENCE_PDF
from backend.schemas import (
    CandidatePolicyAnalysisRequest,
    CandidatePolicyAnalysisResponse,
    PolicyBatchValidationRequest,
    PolicyFeasibilityRequest,
    RagQuestionRequest,
    ReportGenerateRequest,
)
from backend.uploads import UploadTooLargeError, persist_upload
from tianshu_core.config import load_config
from tianshu_core.llm.client import get_model_settings
from tianshu_core.rag.config import settings_from_config as rag_settings_from_config
from tianshu_core.rag.library import (
    get_policy_document,
    list_policy_library,
    search_policy_library,
)
from tianshu_core.rag.policy_service import (
    analyze_candidate_policy_feasibility,
    analyze_policy_feasibility,
    answer_policy_question,
    validate_policy_feasibility_batch,
)

policy_api = Blueprint("policy_api", __name__)


def _rag_settings():
    return rag_settings_from_config(load_config())


@policy_api.post("/policies/upload")
def upload_policy_documents():
    files = request.files.getlist("files")
    if not files or not any(file.filename for file in files):
        raise ApiError(400, "请至少上传一个政策文件")
    workspace = workspace_service()
    for file in files:
        name = file.filename or "policy-document"
        suffix = name.rsplit(".", maxsplit=1)[-1].lower() if "." in name else ""
        if suffix not in {"doc", "docx", "txt"}:
            raise ApiError(400, "政策文件当前支持DOC、DOCX或TXT")
        try:
            upload_path, size = persist_upload(file, name)
            workspace.add_policy_document(name, upload_path, size)
        except UploadTooLargeError as exc:
            raise ApiError(413, str(exc)) from exc
        except (ValueError, TypeError, zipfile.BadZipFile) as exc:
            raise ApiError(422, f"政策文件解析失败：{exc}") from exc
    return json_response(workspace.summary())


@policy_api.post("/reports/policy-pdf")
def generate_policy_report():
    payload = parse_body(ReportGenerateRequest)
    workspace = workspace_service()
    if workspace.latest_analysis_payload is None:
        raise ApiError(409, "请先完成一次候选地块分析，再生成政策PDF")
    try:
        model_settings = get_model_settings(payload.model_id)
    except KeyError as exc:
        raise ApiError(422, str(exc)) from exc
    return json_response(workspace.add_policy_report_pdf(model_settings))


@policy_api.get("/policies/reference-pdf/preview")
def preview_policy_reference_pdf():
    if not POLICY_REFERENCE_PDF.exists():
        raise ApiError(404, "政策参考PDF不存在")
    return send_file(
        POLICY_REFERENCE_PDF,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=POLICY_REFERENCE_PDF.name,
    )


@policy_api.get("/rag/policies")
def list_rag_policy_documents():
    return json_response(list_policy_library(_rag_settings()))


@policy_api.get("/rag/policies/<document_id>")
def get_rag_policy_document(document_id: str):
    document = get_policy_document(_rag_settings(), document_id)
    if document is None:
        raise ApiError(404, "RAG政策文档不存在")
    return json_response(document)


@policy_api.get("/rag/search")
def search_rag_policies():
    query = (request.args.get("q") or "").strip()
    if not query or len(query) > 200:
        raise ApiError(422, "检索内容长度必须为1到200个字符")
    limit = integer_query("limit", 8, minimum=1, maximum=30)
    return json_response(search_policy_library(_rag_settings(), query, limit))


@policy_api.post("/rag/ask")
def ask_rag_question():
    payload = parse_body(RagQuestionRequest)
    try:
        result = answer_policy_question(
            payload.question,
            _rag_settings(),
            get_model_settings(payload.model_id),
        )
    except (FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        raise ApiError(422, str(exc)) from exc
    return json_response(result)


@policy_api.post("/rag/feasibility")
def analyze_rag_feasibility():
    payload = parse_body(PolicyFeasibilityRequest)
    try:
        parcel = workspace_service().enrich_parcel_attributes(payload.parcel)
        result = analyze_policy_feasibility(
            parcel,
            _rag_settings(),
            get_model_settings(payload.model_id),
        )
    except (FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        raise ApiError(422, str(exc)) from exc
    return json_response(result)


@policy_api.post("/rag/feasibility/batch")
def validate_rag_feasibility_batch():
    payload = parse_body(PolicyBatchValidationRequest)
    try:
        workspace = workspace_service()
        enriched_cases = []
        for raw_case in payload.test_cases:
            case = dict(raw_case)
            key = "parcel" if isinstance(case.get("parcel"), dict) else "land_attrs"
            parcel = case.get(key) if isinstance(case.get(key), dict) else {}
            case[key] = workspace.enrich_parcel_attributes(parcel)
            enriched_cases.append(case)
        result = validate_policy_feasibility_batch(
            enriched_cases,
            _rag_settings(),
            get_model_settings(payload.model_id),
        )
    except (FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        raise ApiError(422, str(exc)) from exc
    return json_response(result)


def _candidate_analysis(payload: CandidatePolicyAnalysisRequest, progress_callback=None):
    workspace = workspace_service()
    candidates = workspace.candidate_parcels()
    if candidates.analysis_required or not candidates.parcels:
        raise ApiError(422, "当前没有候选地块，请先运行候选地块分析。")
    try:
        result = analyze_candidate_policy_feasibility(
            candidates.parcels,
            _rag_settings(),
            get_model_settings(payload.model_id),
            progress_callback=progress_callback,
        )
        decisions, spatial, artifact = workspace.apply_candidate_policy_results(
            result["results"], result["report"]
        )
    except (FileNotFoundError, ValueError, RuntimeError, KeyError) as exc:
        raise ApiError(422, str(exc)) from exc
    return CandidatePolicyAnalysisResponse(
        **result,
        decisions=decisions,
        spatial=spatial,
        artifact=artifact,
    )


@policy_api.post("/rag/candidates/feasibility")
def analyze_candidate_feasibility():
    return json_response(_candidate_analysis(parse_body(CandidatePolicyAnalysisRequest)))


@policy_api.post("/rag/candidates/feasibility/stream")
def stream_candidate_policy_feasibility():
    payload = parse_body(CandidatePolicyAnalysisRequest)

    def produce(publish):
        result = _candidate_analysis(
            payload,
            progress_callback=lambda progress: publish({"type": "progress", "progress": progress}),
        )
        publish({"type": "result", "result": result})

    return ndjson_response(produce, error_prefix="候选地块政策可行性分析失败")
