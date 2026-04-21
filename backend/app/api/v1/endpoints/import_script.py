# backend/app/api/v1/endpoints/import_script.py
"""
Sprint 5 — Unified Import Endpoints
Supports: Postman Collection, OpenAPI/Swagger, SOAP/WSDL, Chrome Extension recording
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
import json
import logging

from app.db.session import get_db
from app.core.security import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

# ─── Chrome Extension: in-memory pending requests by session_id ───────────────
_chrome_sessions: dict[str, list[dict]] = {}


# ─── Postman Import ───────────────────────────────────────────────────────────

@router.post("/postman")
async def import_postman(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Import a Postman Collection (v2.0 / v2.1) JSON file."""
    from app.services.engine.postman_importer import PostmanImporter

    if not file.filename or not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a .json Postman Collection")

    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    try:
        importer = PostmanImporter()
        script_model, stats = importer.import_collection(content_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Postman import error: {e}")
        raise HTTPException(status_code=500, detail="Error processing Postman collection")

    return {"script_model": script_model, "stats": stats, "source": "postman"}


# ─── OpenAPI / Swagger Import ─────────────────────────────────────────────────

@router.post("/openapi")
async def import_openapi(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Import an OpenAPI 3.x or Swagger 2.0 spec (JSON or YAML)."""
    from app.services.engine.openapi_importer import OpenAPIImporter

    valid_ext = ('.json', '.yaml', '.yml')
    if file.filename and not any(file.filename.endswith(ext) for ext in valid_ext):
        raise HTTPException(status_code=400, detail="File must be .json, .yaml, or .yml")

    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    try:
        importer = OpenAPIImporter()
        script_model, stats = importer.import_spec(content_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"OpenAPI import error: {e}")
        raise HTTPException(status_code=500, detail="Error processing OpenAPI spec")

    return {"script_model": script_model, "stats": stats, "source": "openapi"}


# ─── WSDL / SOAP Import ──────────────────────────────────────────────────────

@router.post("/wsdl")
async def import_wsdl(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Import a SOAP/WSDL XML file."""
    from app.services.engine.wsdl_importer import WSDLImporter

    valid_ext = ('.wsdl', '.xml')
    if file.filename and not any(file.filename.endswith(ext) for ext in valid_ext):
        raise HTTPException(status_code=400, detail="File must be .wsdl or .xml")

    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")

    try:
        importer = WSDLImporter()
        script_model, stats = importer.import_wsdl(content_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"WSDL import error: {e}")
        raise HTTPException(status_code=500, detail="Error processing WSDL file")

    return {"script_model": script_model, "stats": stats, "source": "wsdl"}


# ─── Chrome Extension Endpoints ──────────────────────────────────────────────

class ChromePushRequest(BaseModel):
    session_id: str
    requests: List[dict]


@router.post("/chrome/push")
async def chrome_push(
    payload: ChromePushRequest,
    current_user=Depends(get_current_user),
):
    """Receive recorded requests from Chrome Extension."""
    sid = payload.session_id
    if sid not in _chrome_sessions:
        _chrome_sessions[sid] = []

    _chrome_sessions[sid].extend(payload.requests)
    logger.info(f"Chrome push: session={sid}, +{len(payload.requests)} requests, total={len(_chrome_sessions[sid])}")

    return {
        "status": "ok",
        "session_id": sid,
        "total_requests": len(_chrome_sessions[sid]),
    }


@router.get("/chrome/pending/{session_id}")
async def chrome_pending(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """Poll pending requests from a Chrome recording session. Frontend polls this."""
    requests = _chrome_sessions.get(session_id, [])
    return {
        "session_id": session_id,
        "total_requests": len(requests),
        "requests": requests,
    }


@router.post("/chrome/convert/{session_id}")
async def chrome_convert(
    session_id: str,
    current_user=Depends(get_current_user),
):
    """Convert Chrome-recorded requests into Script Model and clear session."""
    from app.services.engine.har_importer import HARImporter, STATIC_EXTENSIONS, FILTER_DOMAINS

    raw_requests = _chrome_sessions.pop(session_id, [])
    if not raw_requests:
        raise HTTPException(status_code=404, detail="No requests found for this session")

    import uuid
    from pathlib import Path

    requests = []
    stats = {"total_captured": len(raw_requests), "imported": 0, "filtered": 0}

    for i, raw in enumerate(raw_requests):
        url = raw.get("url", "")
        method = raw.get("method", "GET").upper()

        # Filter static resources
        path = url.split("?")[0].split("#")[0]
        ext = Path(path).suffix.lower()
        if ext in STATIC_EXTENSIONS:
            stats["filtered"] += 1
            continue

        # Filter trackers
        url_lower = url.lower()
        if any(domain in url_lower for domain in FILTER_DOMAINS):
            stats["filtered"] += 1
            continue

        # Build request
        headers = raw.get("requestHeaders", {})
        body = raw.get("requestBody", "")
        body_type = "raw"
        content_type = headers.get("Content-Type", headers.get("content-type", ""))
        if "json" in content_type:
            body_type = "json"
        elif "xml" in content_type:
            body_type = "xml"
        elif "form" in content_type:
            body_type = "form"

        # Request name from path
        path_segments = [s for s in path.split("/") if s]
        name = f"{method} /{'/'.join(path_segments[-2:])}" if path_segments else f"{method} /"

        status_code = str(raw.get("statusCode", 200))
        assertions = []
        if status_code and status_code != "0":
            assertions.append({"type": "status_code", "value": status_code})

        requests.append({
            "id": str(uuid.uuid4()),
            "order": len(requests),
            "name": name,
            "protocol": "http",
            "method": method,
            "url": url,
            "headers": {k: v for k, v in headers.items()
                        if k.lower() not in ('host', 'content-length', 'connection', 'accept-encoding')},
            "body": body if isinstance(body, str) else json.dumps(body) if body else "",
            "body_type": body_type,
            "params": {},
            "assertions": assertions,
            "think_time_ms": 0,
            "extractors": [],
        })
        stats["imported"] += 1

    script_model = {
        "requests": requests,
        "variables": [],
        "data_files": [],
        "protocol": "http",
    }

    return {"script_model": script_model, "stats": stats, "source": "chrome"}
