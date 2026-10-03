import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Asset, Attachment, User
from ..ocr import extract_text, ocr_available, parse_fields
from ..schemas import AttachmentOut, AttachmentUpdate, ExtractedFields, UploadResult
from ..security import audit, get_current_user
from ..storage import abs_path, delete_files, save_upload
from .assets import attachment_out

router = APIRouter(prefix="/attachments", tags=["attachments"])
log = logging.getLogger("attachments")
KINDS = {"invoice", "warranty_card", "photo", "manual", "receipt", "other"}


def _get(db: Session, att_id: int) -> Attachment:
    a = db.get(Attachment, att_id)
    if not a:
        raise HTTPException(404, "Attachment not found")
    return a


async def _extract(att: Attachment) -> ExtractedFields | None:
    if att.content_type != "application/pdf" and not ocr_available():
        return None
    try:
        text = await run_in_threadpool(extract_text, abs_path(att.stored_path), att.content_type)
    except Exception as e:
        log.warning("OCR failed for attachment %s: %s", att.id, e)
        return None
    att.ocr_text = text[:100_000] if text else None
    return parse_fields(text or "")


@router.post("", response_model=UploadResult, status_code=201)
async def upload(file: UploadFile = File(...), kind: str = Form("invoice"),
                 asset_id: int | None = Form(None), extract: bool = Form(False),
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Upload an invoice/photo. Without asset_id it is a draft that gets linked when the asset is saved.
    With extract=true the text is read (OCR/pdftotext) and suggested field values are returned."""
    if kind not in KINDS:
        raise HTTPException(400, "Invalid kind")
    if asset_id and not db.get(Asset, asset_id):
        raise HTTPException(404, "Asset not found")
    stored = await save_upload(file)
    dup = db.scalar(select(Attachment.asset_id).where(Attachment.sha256 == stored.sha256,
                                                     Attachment.asset_id.is_not(None)).limit(1))
    att = Attachment(asset_id=asset_id, kind=kind, original_filename=stored.original_filename,
                     stored_path=stored.stored_path, thumb_path=stored.thumb_path,
                     content_type=stored.content_type, size_bytes=stored.size_bytes,
                     sha256=stored.sha256, uploaded_by=user.id)
    db.add(att)
    db.flush()
    extracted = await _extract(att) if extract else None
    audit(db, user.id, "attachment.upload", "attachment", att.id, asset_id=asset_id)
    db.commit()
    return UploadResult(attachment=attachment_out(att), extracted=extracted,
                        ocr_available=ocr_available(), duplicate_of_asset_id=dup)


@router.post("/{att_id}/extract", response_model=ExtractedFields)
async def re_extract(att_id: int, db: Session = Depends(get_db)):
    att = _get(db, att_id)
    fields = await _extract(att)
    db.commit()
    if fields is None:
        raise HTTPException(503, "Text extraction is not available")
    return fields


def _serve(path_rel: str, ctype: str, filename: str, download: bool):
    p = abs_path(path_rel)
    if not p.exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(p, media_type=ctype, filename=filename,
                        content_disposition_type="attachment" if download else "inline",
                        headers={"Cache-Control": "private, max-age=86400",
                                 "X-Content-Type-Options": "nosniff"})


@router.get("/{att_id}/file")
def get_file(att_id: int, download: bool = False, db: Session = Depends(get_db)):
    a = _get(db, att_id)
    return _serve(a.stored_path, a.content_type, a.original_filename, download)


@router.get("/{att_id}/thumb")
def get_thumb(att_id: int, db: Session = Depends(get_db)):
    a = _get(db, att_id)
    if not a.thumb_path:
        raise HTTPException(404, "No thumbnail")
    return _serve(a.thumb_path, "image/jpeg", "thumb.jpg", False)


@router.patch("/{att_id}", response_model=AttachmentOut)
def update_attachment(att_id: int, body: AttachmentUpdate, db: Session = Depends(get_db)):
    a = _get(db, att_id)
    data = body.model_dump(exclude_unset=True)
    if "asset_id" in data and data["asset_id"] and not db.get(Asset, data["asset_id"]):
        raise HTTPException(404, "Asset not found")
    for k, v in data.items():
        setattr(a, k, v)
    db.commit()
    return attachment_out(a)


@router.delete("/{att_id}", status_code=204)
def delete_attachment(att_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = _get(db, att_id)
    paths = (a.stored_path, a.thumb_path)
    audit(db, user.id, "attachment.delete", "attachment", a.id, asset_id=a.asset_id)
    db.delete(a)
    db.commit()
    delete_files(*paths)
