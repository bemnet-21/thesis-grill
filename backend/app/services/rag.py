"""RAG service — PDF ingestion, chunking, embedding, and retrieval."""

import logging
import uuid

from langchain_community.document_loaders import PyPDFLoader
from langchain_voyageai import VoyageAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Thesis, ThesisChunk
from app.services.storage import download_pdf

logger = logging.getLogger(__name__)

_embeddings = None


def _get_embeddings() -> VoyageAIEmbeddings:
    """Lazy-init the embeddings model."""
    global _embeddings
    if _embeddings is None:
        _embeddings = VoyageAIEmbeddings(
            voyage_api_key=settings.VOYAGE_API_KEY,
            model=settings.EMBEDDING_MODEL,
        )
    return _embeddings


def ingest_thesis(thesis_id: uuid.UUID, pdf_path: str, db: Session) -> None:
    """Background worker: parse PDF → chunk → embed → store in pgvector.

    Updates thesis.ingestion_status through the pipeline stages.
    """
    thesis = db.get(Thesis, thesis_id)
    if thesis is None:
        logger.error("Thesis %s not found", thesis_id)
        return

    local_pdf_path = None
    try:
        # 0. Download PDF if needed
        local_pdf_path = download_pdf(pdf_path)

        # 1. Load PDF
        loader = PyPDFLoader(local_pdf_path)
        pages = loader.load()

        # 2. Split into chunks (target 500-800 tokens, ~600 avg)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2400,       # ~600 tokens × 4 chars/token
            chunk_overlap=400,     # ~100 tokens overlap
            length_function=len,
        )
        docs = splitter.split_documents(pages)

        thesis.ingestion_status = "chunked"
        db.commit()

        # 3. Embed all chunks
        texts = [doc.page_content for doc in docs]
        embeddings_model = _get_embeddings()
        vectors = embeddings_model.embed_documents(texts)

        thesis.ingestion_status = "embedded"
        db.commit()

        # 4. Store chunks with embeddings
        for doc, vector in zip(docs, vectors):
            section = doc.metadata.get("page", None)
            chunk = ThesisChunk(
                thesis_id=thesis_id,
                section_label=f"page_{section}" if section is not None else None,
                text=doc.page_content,
                embedding=vector,
            )
            db.add(chunk)

        thesis.ingestion_status = "ready"
        db.commit()
        logger.info("Thesis %s ingestion complete — %d chunks", thesis_id, len(docs))

    except Exception:
        logger.exception("Ingestion failed for thesis %s", thesis_id)
        thesis.ingestion_status = "failed"
        db.commit()
    finally:
        # Clean up temporary file if it was downloaded from S3
        if local_pdf_path and local_pdf_path != pdf_path:
            try:
                os.remove(local_pdf_path)
            except OSError:
                logger.warning("Failed to remove temporary PDF file: %s", local_pdf_path)


def retrieve(
    thesis_id: uuid.UUID, query: str, db: Session, k: int = 4
) -> list[str]:
    """Embed the query and return the top-k most similar chunk texts."""
    embeddings_model = _get_embeddings()
    query_vector = embeddings_model.embed_query(query)

    # pgvector cosine distance: smaller <=> value = more similar
    vector_literal = f"[{','.join(str(v) for v in query_vector)}]"
    result = db.execute(
        text(
            """
            SELECT text
            FROM thesis_chunks
            WHERE thesis_id = :thesis_id
            ORDER BY embedding <=> :query_vec
            LIMIT :k
            """
        ),
        {"thesis_id": str(thesis_id), "query_vec": vector_literal, "k": k},
    )
    return [row[0] for row in result.fetchall()]
