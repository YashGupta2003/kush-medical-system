from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.deps import require_owner
from app.services import gst_report_service

router = APIRouter(prefix="/gst", dependencies=[Depends(require_owner)], tags=["gst"])


@router.get("/report", response_model=schemas.GstReport)
def gst_report(
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
):
    """Owner-only: GST slab-wise breakdown for a given month (defaults to current month)."""
    today = date.today()
    return gst_report_service.get_gst_report(db, year or today.year, month or today.month)


@router.get("/report/pdf")
def gst_report_pdf(
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
):
    """Owner-only: same report, rendered as a downloadable PDF for the CA."""
    today = date.today()
    y, m = year or today.year, month or today.month
    report = gst_report_service.get_gst_report(db, y, m)
    pdf_bytes = gst_report_service.generate_gst_report_pdf(report)

    filename = f"GST_Report_{report['month_label'].replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )