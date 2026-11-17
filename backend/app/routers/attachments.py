"""US-13: As an end user, I want to attach files to a ticket so that I can provide
screenshots or supporting evidence.

Upload rules
- Allowed types: common images, PDF, plain text/logs/CSV, and Office documents.
- Each file is at most 5 MB (ATTACHMENT_MAX_MB) and a ticket holds at most 10 files.
- The file's content must match its extension (magic-byte check), so a renamed
  executable is rejected. The served Content-Type comes from the extension, never
  from the client.
- Files are stored on disk under random names, outside any web root, and are only
  downloadable by users who can view the ticket. Closed tickets accept no new files.
"""
import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import get_visible_ticket
from ..activity import record
from ..database import get_db
from ..models import Attachment, EventKind, Status, User
from ..schemas import AttachmentOut
from ..security import get_current_user

router = APIRouter(prefix="/api", tags=["attachments"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
MAX_ATTACHMENT_BYTES = int(float(os.getenv("ATTACHMENT_MAX_MB", "5")) * 1024 * 1024)
MAX_ATTACHMENTS_PER_TICKET = 10
CHUNK = 64 * 1024

_TEXT = "text"
_ZIP = (b"PK\x03\x04",)
# extension -> (served content type, accepted leading signatures or _TEXT)
ALLOWED_EXTENSIONS: dict[str, tuple[str, tuple[bytes, ...] | str]] = {
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "gif": ("image/gif", (b"GIF87a", b"GIF89a")),
    "webp": ("image/webp", (b"RIFF",)),
    "pdf": ("application/pdf", (b"%PDF-",)),
    "txt": ("text/plain", _TEXT),
    "log": ("text/plain", _TEXT),
    "csv": ("text/csv", _TEXT),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", _ZIP),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _ZIP),
}


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _content_matches(ext: str, head: bytes) -> bool:
    rule = ALLOWED_EXTENSIONS[ext][1]
    if rule == _TEXT:
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
        except UnicodeDecodeError as e:
            # A multi-byte character may be cut off at the end of the sniffed chunk.
            return e.start >= len(head) - 3
        return True
    if ext == "webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return any(head.startswith(sig) for sig in rule)


def _clean_name(filename: str) -> str:
    name = os.path.basename(filename.replace("\\", "/")).strip()
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    return name[-200:] or "attachment"


@router.get("/tickets/{ticket_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_visible_ticket(db, ticket_id, user)
    return db.scalars(
        select(Attachment).where(Attachment.ticket_id == ticket_id).order_by(Attachment.created_at, Attachment.id)
    ).all()


@router.post("/tickets/{ticket_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = get_visible_ticket(db, ticket_id, user)
    if ticket.status == Status.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Closed tickets do not accept new attachments")
    count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.ticket_id == ticket_id))
    if count >= MAX_ATTACHMENTS_PER_TICKET:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A ticket can have at most {MAX_ATTACHMENTS_PER_TICKET} attachments")

    filename = _clean_name(file.filename or "")
    ext = _extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"File type not allowed. Allowed types: {allowed}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = secrets.token_hex(16)
    path = UPLOAD_DIR / stored_name
    size = 0
    try:
        with path.open("wb") as out:
            first = True
            while chunk := await file.read(CHUNK):
                if first:
                    if not _content_matches(ext, chunk[:4096]):
                        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"File content does not match a .{ext} file")
                    first = False
                size += len(chunk)
                if size > MAX_ATTACHMENT_BYTES:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"File is larger than the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB limit",
                    )
                out.write(chunk)
        if size == 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "File is empty")
    except BaseException:
        path.unlink(missing_ok=True)
        raise

    attachment = Attachment(
        ticket_id=ticket.id,
        uploaded_by_id=user.id,
        filename=filename,
        stored_name=stored_name,
        content_type=ALLOWED_EXTENSIONS[ext][0],
        size=size,
    )
    db.add(attachment)
    record(db, ticket, user, EventKind.ATTACHMENT, f"{user.full_name} attached {filename}")
    try:
        db.commit()
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    db.refresh(attachment)
    return attachment


@router.get("/attachments/{attachment_id}")
def download_attachment(attachment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    get_visible_ticket(db, attachment.ticket_id, user)  # 404s if the user cannot see the ticket
    path = UPLOAD_DIR / attachment.stored_name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment file is missing")
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,  # sent as Content-Disposition: attachment
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
