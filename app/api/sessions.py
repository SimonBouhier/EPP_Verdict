"""
LYRA CLEAN - SESSIONS & PROFILES API
====================================

Endpoints for session management and Bezier profile configuration.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.models import (
    SessionCreateRequest,
    SessionResponse,
    SessionHistoryResponse,
    ProfileResponse,
    ProfileListResponse,
    format_timestamp
)
from database import get_db, ISpaceDB
from core.physics import BezierEngine


router = APIRouter(tags=["sessions"])


# ============================================================================
# DEPENDENCIES
# ============================================================================

async def get_database() -> ISpaceDB:
    """Dependency: Database instance."""
    return await get_db()


# ============================================================================
# SESSION ENDPOINTS
# ============================================================================

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: SessionCreateRequest,
    db: ISpaceDB = Depends(get_database)
):
    """
    Create new conversation session.

    Example:
        POST /sessions
        {
            "profile": "creative",
            "metadata": {"user_id": "user-123"}
        }

    Returns:
        {
            "session_id": "abc-123",
            "profile": "creative",
            "created_at": "2025-01-01T12:00:00Z",
            "message_count": 0
        }
    """
    session_id = str(uuid.uuid4())

    # Verify profile exists
    profile = await db.get_profile(request.profile)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail=f"Profile '{request.profile}' not found"
        )

    # Create session
    await db.create_session(
        session_id=session_id,
        profile=request.profile,
        params_snapshot=None  # TODO: Add metadata support
    )

    # Get session data
    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT created_at, last_activity FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        row = await cursor.fetchone()

    return SessionResponse(
        session_id=session_id,
        profile=request.profile,
        created_at=format_timestamp(row[0]),
        last_activity=format_timestamp(row[1]),
        message_count=0,
        total_tokens=0
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: ISpaceDB = Depends(get_database)
):
    """
    Get session information.

    Example:
        GET /sessions/abc-123

    Returns:
        {
            "session_id": "abc-123",
            "profile": "creative",
            "created_at": "2025-01-01T12:00:00Z",
            "message_count": 15
        }
    """
    async with db.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT s.profile, s.created_at, s.last_activity, s.message_count, s.total_tokens
            FROM sessions s
            WHERE s.session_id = ?
            """,
            (session_id,)
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found"
        )

    return SessionResponse(
        session_id=session_id,
        profile=row[0],
        created_at=format_timestamp(row[1]),
        last_activity=format_timestamp(row[2]),
        message_count=row[3],
        total_tokens=row[4]
    )


@router.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str,
    limit: int = 50,
    db: ISpaceDB = Depends(get_database)
):
    """
    Get conversation history for session.

    Example:
        GET /sessions/abc-123/history?limit=20

    Returns:
        {
            "session_id": "abc-123",
            "messages": [
                {"role": "user", "content": "Hello", "timestamp": "...", "event_id": 1},
                {"role": "assistant", "content": "Hi!", "timestamp": "...", "event_id": 2}
            ],
            "total_messages": 2
        }
    """
    # Verify session exists
    async with db.connection() as conn:
        cursor = await conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        exists = await cursor.fetchone() is not None

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found"
        )

    # Get history
    events = await db.get_session_history(
        session_id=session_id,
        limit=limit,
        event_types=['user_message', 'assistant_message']
    )

    # Format messages
    messages = []
    for event in events:
        messages.append({
            "event_id": event["event_id"],
            "role": event["role"],
            "content": event["content"],
            "timestamp": format_timestamp(event["timestamp"]),
            "latency_ms": event.get("latency_ms")
        })

    return SessionHistoryResponse(
        session_id=session_id,
        messages=messages,
        total_messages=len(messages)
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: ISpaceDB = Depends(get_database)
):
    """
    Delete session and all associated data.

    Example:
        DELETE /sessions/abc-123

    Returns:
        {"status": "deleted", "session_id": "abc-123"}
    """
    async with db.connection() as conn:
        # Check if session exists
        cursor = await conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        exists = await cursor.fetchone() is not None

        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Session '{session_id}' not found"
            )

        # Delete (CASCADE will delete events and trajectories)
        await conn.execute(
            "DELETE FROM sessions WHERE session_id = ?",
            (session_id,)
        )
        await conn.commit()

    return {
        "status": "deleted",
        "session_id": session_id
    }


# ============================================================================
# PROFILE ENDPOINTS
# ============================================================================

@router.get("/profiles", response_model=ProfileListResponse)
async def list_profiles(db: ISpaceDB = Depends(get_database)):
    """
    List all available Bezier profiles.

    Example:
        GET /profiles

    Returns:
        {
            "profiles": [
                {"name": "balanced", "description": "...", "is_default": true},
                {"name": "creative", "description": "...", "is_default": false}
            ]
        }
    """
    profiles = await db.list_profiles()

    return ProfileListResponse(profiles=profiles)


@router.get("/profiles/{profile_name}", response_model=ProfileResponse)
async def get_profile(
    profile_name: str,
    include_preview: bool = False,
    preview_samples: int = 10,
    db: ISpaceDB = Depends(get_database)
):
    """
    Get Bezier profile configuration.

    Args:
        profile_name: Profile identifier (e.g., "creative")
        include_preview: Generate trajectory preview
        preview_samples: Number of sample points for preview

    Example:
        GET /profiles/creative?include_preview=true

    Returns:
        {
            "profile_name": "creative",
            "description": "High exploration...",
            "tau_c_curve": [[0, 1.3], [0.3, 1.5], ...],
            "preview": [
                {"t": 0.0, "tau_c": 1.30, "rho": 0.50},
                {"t": 0.5, "tau_c": 1.45, "rho": 0.65}
            ]
        }
    """
    profile = await db.get_profile(profile_name)

    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Profile '{profile_name}' not found"
        )

    # Generate preview if requested
    preview = None
    if include_preview:
        try:
            engine = BezierEngine.from_profile(profile)
            trajectory = engine.sample_trajectory(num_points=preview_samples)

            preview = [state.to_dict() for state in trajectory]

        except Exception as e:
            # Profile malformed, skip preview
            preview = [{"error": str(e)}]

    return ProfileResponse(
        profile_name=profile["profile_name"],
        description=profile["description"],
        tau_c_curve=profile["tau_c_curve"],
        rho_curve=profile["rho_curve"],
        delta_r_curve=profile["delta_r_curve"],
        kappa_curve=profile.get("kappa_curve"),
        is_default=bool(profile.get("is_default", False)),
        preview=preview
    )
