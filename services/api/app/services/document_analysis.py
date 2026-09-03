"""Document pipeline service - analysis endpoint helpers.

Wires the document processing pipeline into the API layer. Stores
structured analysis (quality, type, OCR, MRZ, extracted fields) back
onto the DocumentRecord.
"""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.storage import download_file
from app.models.models import DocumentRecord
from app.pipeline.pipeline import analyze_document, load_image

settings = get_settings()
logger = structlog.get_logger()


async def run_document_analysis(db: AsyncSession, document: DocumentRecord) -> dict:
    """Download a stored document, run the analysis pipeline, persist results."""
    data = download_file(settings.MINIO_BUCKET, str(document.storage_key))
    image = load_image(data)

    analysis = analyze_document(image)

    # Persist structured results back to the record
    document.document_type = analysis.document_type  # type: ignore[assignment]
    document.quality_score = analysis.quality.get("overall_score", 0.0)  # type: ignore[assignment]
    document.ocr_data = {  # type: ignore[assignment]
        "text": analysis.ocr_text,
        "engine": analysis.ocr_engine,
        "confidence": analysis.ocr_confidence,
        "words": analysis.ocr_words,
    }
    document.mrz_data = analysis.mrz  # type: ignore[assignment]
    document.extracted_fields = analysis.extracted_fields  # type: ignore[assignment]

    await db.commit()
    await db.refresh(document)

    result = {
        "document_id": str(document.id),
        "document_type": analysis.document_type,
        "type_confidence": analysis.type_confidence,
        "quality": analysis.quality,
        "dimensions": {"width": analysis.width, "height": analysis.height},
        "ocr": {
            "engine": analysis.ocr_engine,
            "confidence": analysis.ocr_confidence,
        },
        "mrz": analysis.mrz,
        "extracted_fields": analysis.extracted_fields,
        "preprocessing_stages": analysis.preprocessing_stages,
    }
    logger.info(
        "document_analyzed",
        document_id=str(document.id),
        document_type=analysis.document_type,
        quality=analysis.quality.get("overall_score"),
    )
    return result
