import filetype
from fastapi import HTTPException, UploadFile
from app.config import settings

def validate_upload(file: UploadFile) -> bytes:
    """
    Validates file size and magic bytes. Returns the file content.
    Raises HTTPException(413) if too large, 400 if invalid type.
    """
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"File too large. Maximum allowed size is {settings.max_upload_size_mb}MB.")
    
    # Check magic bytes
    kind = filetype.guess(content)
    if not kind or kind.mime not in ["image/jpeg", "image/png", "application/pdf"]:
        raise HTTPException(400, "Only JPEG, PNG and PDF files are allowed. Invalid file content.")
    
    return content

def validate_audio_upload(file: UploadFile) -> tuple[bytes, str]:
    """
    Validates audio file size and magic bytes. Returns (content, mime_type).
    Raises HTTPException(413) if too large, 400 if invalid type.
    """
    max_bytes = settings.max_voice_upload_size_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(413, f"File too large. Maximum allowed size is {settings.max_voice_upload_size_mb}MB.")
    
    # Check magic bytes using filetype, but fallback to trusting Content-Type
    # for formats filetype might not reliably detect (like raw webm/opus).
    kind = filetype.guess(content)
    mime = kind.mime if kind else file.content_type
    
    allowed_mimes = ["audio/webm", "audio/ogg", "audio/wav", "audio/mp3", "audio/mpeg", "video/webm"]
    # Browsers often send audio recordings as video/webm depending on the container.
    if mime not in allowed_mimes:
        raise HTTPException(400, f"Only WebM, OGG, WAV, and MP3 files are allowed. Invalid file content: {mime}")
    
    return content, mime
