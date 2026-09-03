"""Face verification service.

Performs portrait extraction, face embedding, liveness heuristics, and
face-to-face verification against a provided live face and/or a synthetic
identity database (for duplicate/multiple-identity detection).
"""
from typing import Any, Optional

import numpy as np

from app.core.config import get_settings
from app.face.engine import FaceEngine, cosine_similarity, get_face_engine
from app.face.liveness import liveness_heuristic
from app.face.portrait import extract_portrait

settings = get_settings()


def run_face_analysis(
    document_image: np.ndarray,
    live_face_image: Optional[np.ndarray] = None,
    identity_db_embeddings: Optional[list[dict]] = None,
    face_engine: Optional[FaceEngine] = None,
) -> dict:
    """Complete face verification workflow for a document."""
    engine = face_engine or get_face_engine()

    # 1. Extract portrait from document
    portrait_result = extract_portrait(document_image, face_engine=engine)
    portrait = portrait_result.get("portrait")

    output: dict[str, Any] = {
        "portrait": portrait_result,
        "document_embedding": None,
        "live_embedding": None,
        "verification": None,
        "liveness": None,
        "duplicate_identity": None,
    }

    # 2. Embed the document portrait
    doc_embedding: Optional[list[float]] = None
    if portrait is not None and portrait.size > 0:
        doc_embedding = engine.get_embedding(portrait)
    output["document_embedding"] = doc_embedding

    # 3. If a live face was provided, verify against the portrait
    if live_face_image is not None and doc_embedding:
        live_embedding: Optional[list[float]] = engine.get_embedding(live_face_image)
        output["live_embedding"] = live_embedding
        if live_embedding:
            output["verification"] = engine.verify(doc_embedding, live_embedding)
            # Liveness on the live face
            output["liveness"] = liveness_heuristic(live_face_image)

    # 4. Duplicate / multiple-identity check against the synthetic DB
    if doc_embedding and identity_db_embeddings:
        output["duplicate_identity"] = _check_duplicates(
            doc_embedding, identity_db_embeddings, engine
        )

    return output


def _check_duplicates(
    doc_embedding: list[float],
    identity_db: list[dict],
    engine: FaceEngine,
) -> dict:
    """Compare the document face to identity DB embeddings to flag potential
    duplicate/multiple identities."""
    results = []
    for entry in identity_db:
        emb = entry.get("embedding")
        identity_id = entry.get("identity_id")
        if not emb:
            continue
        sim = cosine_similarity(doc_embedding, emb)
        results.append(
            {
                "identity_id": identity_id,
                "similarity": round(sim, 4),
                "match": sim >= settings.FACE_SIMILARITY_THRESHOLD,
            }
        )

    matches = [r for r in results if r["match"]]
    return {
        "matches_found": len(matches),
        "potential_duplicates": [
            {
                "identity_id": r["identity_id"],
                "similarity": r["similarity"],
                "note": "Potential duplicate / multiple identity. Manual review required.",
            }
            for r in matches
        ],
        "flagged": len(matches) > 0,
    }
