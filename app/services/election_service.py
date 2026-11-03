"""
app/services/election_service.py – status helpers for elections.

sync_statuses() moves:
  scheduled -> active  when NOW() >= start_time
  active    -> closed  when NOW() >  end_time

Call at the start of every request that touches election data.
"""
from app.db import query_all, execute, transaction
from app.services import audit_service


def sync_statuses() -> None:
    """
    Automatically advance election statuses based on the current time.
    Logs every automatic change with actor_type='system'.
    """
    # scheduled -> active
    elections_to_activate = query_all(
        """
        SELECT election_id, title
        FROM elections
        WHERE status = 'scheduled' AND start_time <= NOW()
        """,
    )
    for el in elections_to_activate:
        with transaction():
            execute(
                "UPDATE elections SET status = 'active' WHERE election_id = %s",
                (el["election_id"],),
            )
            audit_service.log(
                actor_type="system",
                actor_id=None,
                action="election_activated",
                entity="election",
                entity_id=el["election_id"],
                details=f"Auto-activated: {el['title']}",
            )

    # active -> closed
    elections_to_close = query_all(
        """
        SELECT election_id, title
        FROM elections
        WHERE status = 'active' AND end_time <= NOW()
        """,
    )
    for el in elections_to_close:
        with transaction():
            execute(
                "UPDATE elections SET status = 'closed' WHERE election_id = %s",
                (el["election_id"],),
            )
            audit_service.log(
                actor_type="system",
                actor_id=None,
                action="election_closed",
                entity="election",
                entity_id=el["election_id"],
                details=f"Auto-closed: {el['title']}",
            )

