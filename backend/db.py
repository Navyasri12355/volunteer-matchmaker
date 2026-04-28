"""
Firebase Admin SDK initialization and Firestore client utilities.

This module initializes the Firebase Admin SDK and provides helper functions
for reading/writing documents to Firestore.

Usage
~~~~~
    from backend.db import get_firestore_client

    db = await get_firestore_client()
    volunteer = await db.get("volunteers/vol-123/profile")
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

logger = logging.getLogger(__name__)

_db_client: Optional[FirestoreClient] = None


def _init_firebase() -> None:
    """Initialize Firebase Admin SDK if not already initialized."""
    if firebase_admin._apps:
        logger.debug("Firebase already initialized")
        return

    try:
        # Try to use ADC (Application Default Credentials) first
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized with Application Default Credentials")
    except Exception as exc:
        logger.warning("Firebase initialization failed (%s) – Firestore operations will fail", exc)
        raise


async def get_firestore_client() -> FirestoreClient:
    """Return the Firestore client (lazy-initialized, singleton)."""
    global _db_client
    if _db_client is None:
        _init_firebase()
        _db_client = firestore.client()
    return _db_client


# ─── Utility functions for common Firestore operations ───────────────────────

async def get_document(path: str) -> Optional[dict[str, Any]]:
    """Fetch a single document by path.

    Args:
        path: Full path like "volunteers/vol-123/profile" or "assignments/asn-456"

    Returns:
        Document data dict, or None if not found.
    """
    db = await get_firestore_client()
    doc = db.document(path).get()
    return doc.to_dict() if doc.exists else None


async def save_document(path: str, data: dict[str, Any]) -> None:
    """Save/update a document.

    Args:
        path: Full document path.
        data: Dictionary to save (will overwrite).
    """
    db = await get_firestore_client()
    db.document(path).set(data)


async def update_document(path: str, updates: dict[str, Any]) -> None:
    """Update specific fields in a document (non-overwriting).

    Args:
        path: Full document path.
        updates: Dictionary of fields to update.
    """
    db = await get_firestore_client()
    db.document(path).update(updates)


async def delete_document(path: str) -> None:
    """Delete a document."""
    db = await get_firestore_client()
    db.document(path).delete()


async def query_documents(collection: str, **filters) -> list[dict[str, Any]]:
    """Query a collection with optional filters.

    Args:
        collection: Collection name (e.g. "volunteers", "assignments").
        **filters: Keyword filters (e.g., status="pending").

    Returns:
        List of document data dicts.
    """
    db = await get_firestore_client()
    query = db.collection(collection)
    for key, value in filters.items():
        query = query.where(key, "==", value)
    return [doc.to_dict() for doc in query.stream()]
