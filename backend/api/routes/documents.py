"""`/sessions/{id}/documents` — upload endpoint.

Saves the uploaded file under data/uploads/<session_id>/ and appends a
DocumentRef to the session's state so POST /sessions/{id}/run can process it.
"""

import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from api.session_store import save_session, sessions
from core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["documents"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
_UPLOAD_DIR = _REPO_ROOT / "data" / "uploads"

DocumentType = Literal["pdf", "docx", "pptx", "xlsx", "image", "social_csv"]

_EXTENSION_TYPES: dict[str, DocumentType] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".csv": "social_csv",
}


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    type: DocumentType


@router.post("/{session_id}/documents", response_model=DocumentResponse)
async def upload_document(session_id: str, file: UploadFile) -> DocumentResponse:
    record = sessions.get(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Session not found")

    suffix = Path(file.filename).suffix.lower()
    doc_type = _EXTENSION_TYPES.get(suffix)
    if doc_type is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type {suffix!r}; expected one of "
                f"{sorted(_EXTENSION_TYPES)}"
            ),
        )

    document_id = str(uuid.uuid4())
    session_dir = _UPLOAD_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    dest_path = session_dir / f"{document_id}_{file.filename}"
    dest_path.write_bytes(await file.read())

    record.state["documents"].append({
        "document_id": document_id,
        "filename": file.filename,
        "type": doc_type,
        "path": str(dest_path),
    })
    save_session(session_id, record)

    logger.info("Uploaded %s (%s) to session %s", file.filename, doc_type, session_id)
    return DocumentResponse(document_id=document_id, filename=file.filename, type=doc_type)
