"""Drinks rotation logic.

Public API
----------
    from apps.payments.drinks import next_drink_payers, sessions_attended_count

    # For a session's drinks card:
    suggestion = next_drink_payers(session)
    # Returns:
    # {
    #   'alcohol':     {'user': <User>, 'last_paid': <date|None>} | None,
    #   'non_alcohol': {'user': <User>, 'last_paid': <date|None>} | None,
    # }

    # For the grace-period badge on profile:
    count = sessions_attended_count(user)   # int
    GRACE_PERIOD = 5
"""

from django.db.models import Max

from apps.sessions.models import Attendance
from .models import DrinkRound

GRACE_PERIOD = 5  # sessions a player must attend before entering rotation


# ── Eligibility ──────────────────────────────────────────────────────────────

def sessions_attended_count(user):
    """Total sessions where the player was marked as attended."""
    return Attendance.objects.filter(
        match_player__user=user, attended=True
    ).count()


def _eligible_users_for_session(session, drink_type):
    """Return Users attending *session* who are eligible for *drink_type* rotation.

    Eligible = attended ≥ GRACE_PERIOD sessions AND attending this session.
    All players (regardless of drink_preference) enter the non_alcohol track;
    only players with drink_preference='alcohol' enter the alcohol track.
    """
    from apps.accounts.models import User

    # Who has voted yes / is confirmed for this session
    attending_ids = set(
        session.sessionplayer_set.values_list('user_id', flat=True)
    )
    if not attending_ids:
        # Fall back to yes-voters if no SessionPlayer rows yet
        if hasattr(session, 'poll'):
            attending_ids = set(
                session.poll.votes.filter(
                    choice='yes').values_list('user_id', flat=True)
            )

    if not attending_ids:
        return []

    # Count attended sessions per user in one query
    from django.db.models import Count
    attendance_counts = dict(
        Attendance.objects.filter(
            match_player__user_id__in=attending_ids, attended=True)
        .values('match_player__user_id')
        .annotate(cnt=Count('id'))
        .values_list('match_player__user_id', 'cnt')
    )

    eligible_ids = [
        uid for uid in attending_ids
        if attendance_counts.get(uid, 0) >= GRACE_PERIOD
    ]

    if not eligible_ids:
        return []

    qs = User.objects.filter(id__in=eligible_ids).order_by('username')
    if drink_type == DrinkRound.ALCOHOL:
        qs = qs.filter(drink_preference='alcohol')
    # non_alcohol track = everyone (no filter on preference)

    return list(qs)


# ── Next-payer algorithm ─────────────────────────────────────────────────────

def _last_paid_map(user_ids, drink_type):
    """Return {user_id: last_paid_date} for users who have ever paid."""
    rows = (
        DrinkRound.objects.filter(payer_id__in=user_ids, drink_type=drink_type)
        .values('payer_id')
        .annotate(last=Max('session__date'))
    )
    return {r['payer_id']: r['last'] for r in rows}


def _suggest_payer(users, drink_type):
    """Pick the user who paid longest ago (never paid = oldest).
    Returns {'user': <User>, 'last_paid': <date|None>} or None."""
    if not users:
        return None

    ids = [u.id for u in users]
    last_paid = _last_paid_map(ids, drink_type)

    def sort_key(u):
        date = last_paid.get(u.id)
        # Never paid sorts before any real date (treat as infinitely old)
        if date is None:
            return (0, u.username)
        return (1, str(date), u.username)

    users_sorted = sorted(users, key=sort_key)
    best = users_sorted[0]
    return {'user': best, 'last_paid': last_paid.get(best.id)}


def next_drink_payers(session):
    """Return suggested payer info for both drink tracks for *session*.

    Return value::

        {
            'alcohol':     {'user': <User>, 'last_paid': <date|None>} | None,
            'non_alcohol': {'user': <User>, 'last_paid': <date|None>} | None,
            'alcohol_already_set':     <DrinkRound|None>,
            'non_alcohol_already_set': <DrinkRound|None>,
        }
    """
    existing = {
        dr.drink_type: dr
        for dr in DrinkRound.objects.filter(session=session).select_related('payer')
    }

    alcohol_users = _eligible_users_for_session(session, DrinkRound.ALCOHOL)
    non_alcohol_users = _eligible_users_for_session(
        session, DrinkRound.NON_ALCOHOL)

    return {
        'alcohol':              _suggest_payer(alcohol_users, DrinkRound.ALCOHOL),
        'non_alcohol':          _suggest_payer(non_alcohol_users, DrinkRound.NON_ALCOHOL),
        'alcohol_already_set':     existing.get(DrinkRound.ALCOHOL),
        'non_alcohol_already_set': existing.get(DrinkRound.NON_ALCOHOL),
        'alcohol_eligible':    alcohol_users,
        'non_alcohol_eligible': non_alcohol_users,
    }
