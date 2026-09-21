"""POST /api/export/{docx|xlsx|pdf} — a file the PM can send."""

import logging
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.export.docx_export import build_docx
from app.export.pdf_export import build_pdf
from app.export.xlsx_export import build_xlsx
from app.models import Documents
from app.security import require_access_code

log = logging.getLogger(__name__)

router = APIRouter(tags=["export"], dependencies=[Depends(require_access_code)])

MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


class ExportRequest(BaseModel):
    documents: Documents
    project_name: str | None = None
    rag: str = "Amber"


def safe_filename(project: str | None, fmt: str) -> str:
    """`StatusReport_<project>_<date>.<ext>`, with anything awkward stripped.

    The project name reaches this from user input, and it goes into a
    Content-Disposition header, so it is reduced to a conservative character set
    rather than trusted.
    """
    stem = re.sub(r"[^A-Za-z0-9]+", "-", (project or "Project")).strip("-") or "Project"
    return f"StatusReport_{stem[:40]}_{date.today().isoformat()}.{fmt}"


@router.post("/api/export/{fmt}")
def export(
    fmt: str,
    payload: ExportRequest,
) -> Response:
    if fmt not in MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format. Choose one of: {', '.join(sorted(MEDIA_TYPES))}.",
        )
    project = payload.project_name or ""
    try:
        if fmt == "docx":
            content = build_docx(payload.documents, project, payload.rag)
        elif fmt == "xlsx":
            content = build_xlsx(payload.documents)
        else:
            content = build_pdf(payload.documents, project, payload.rag)
    except Exception as err:
        log.warning("export failed fmt=%s error=%s", fmt, type(err).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="That file could not be produced. Try another format.",
        ) from err

    filename = safe_filename(project, fmt)
    log.info("export fmt=%s bytes=%d", fmt, len(content))
    return Response(
        content=content,
        media_type=MEDIA_TYPES[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
