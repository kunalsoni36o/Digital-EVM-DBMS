"""
app/services/audit_service.py – writes rows to audit_logs.

IMPORTANT: Never log passwords, receipt codes, or voter choices (candidate_id).
"""
from flask import request
from app.db import execute


def log(
    actor_type: str,
    actor_id: int | None,
    action: str,
    entity: str | None = None,
    entity_id: int | None = None,
    details: str | None = None,
) -> None:
    """
    Insert one row into audit_logs.

    Parameters
    ----------
    actor_type : 'admin' | 'voter' | 'system'
    actor_id   : primary key of the actor, or None for system actions
    action     : short verb, e.g. 'vote_cast', 'voter_approved'
    entity     : table/resource name, e.g. 'voter', 'election'
    entity_id  : PK of the affected row
    details    : optional human-readable context (no secrets, no candidate choice)
    """
    try:
        ip = request.remote_addr
    except RuntimeError:
        # Outside of request context (e.g. during init_db)
        ip = None

    execute(
        """
        INSERT INTO audit_logs
            (actor_type, actor_id, action, entity, entity_id, details, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (actor_type, actor_id, action, entity, entity_id, details, ip),
    )

