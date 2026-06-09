"""Player rating engine.

Computes PlayerSessionStat rows from the Delivery ledger for all matches in a
session, then recalculates batting_rating / bowling_rating / fielding_rating on
each User from their full history of PlayerSessionStat rows.

Entry point
-----------
    from apps.matches.rating_engine import compute_session_ratings
    compute_session_ratings(session)   # call after a session is finalised

Rating scale: 0–5 for all three skills.
Weighted average uses rank-based weights across ALL sessions played:
  most recent session = weight N, oldest = weight 1  (N = total sessions played).
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from . import scoring
from .models import Delivery, Player, PlayerSessionStat


# ── Stat derivation ──────────────────────────────────────────────────────────

def _collect_session_stats(session):
    """Return {user_id: dict} with raw aggregated stats across all matches
    in the session. Only users who appeared as a Player in a match are included."""

    stats = {}  # user_id → {...}

    def _ensure(user):
        if user.id not in stats:
            stats[user.id] = {
                'user': user,
                'runs': 0, 'balls_faced': 0,
                'wickets': 0, 'balls_bowled': 0, 'runs_conceded': 0,
                'catches': 0, 'stumpings': 0,
            }

    for match in session.matches.prefetch_related('teams__players__user', 'innings').all():
        for innings in match.innings.all():
            # Batting
            for row in scoring.batting_card(innings):
                user = row['player'].user
                _ensure(user)
                stats[user.id]['runs'] += row['runs']
                stats[user.id]['balls_faced'] += row['balls']

            # Bowling
            for row in scoring.bowling_card(innings):
                user = row['player'].user
                _ensure(user)
                stats[user.id]['wickets'] += row['wickets']
                stats[user.id]['balls_bowled'] += row['balls']
                stats[user.id]['runs_conceded'] += row['runs']

            # Fielding: catches + stumpings
            fielding_qs = (
                innings.deliveries
                .filter(is_wicket=True, dismissal_type__in=('caught', 'stumped'))
                .exclude(fielder__isnull=True)
                .select_related('fielder__user')
            )
            for d in fielding_qs:
                user = d.fielder.user
                _ensure(user)
                if d.dismissal_type == 'caught':
                    stats[user.id]['catches'] += 1
                else:
                    stats[user.id]['stumpings'] += 1

        # Ensure every player on the match roster appears (even with 0s)
        for team in match.teams.prefetch_related('players__user').all():
            for player in team.players.select_related('user').all():
                _ensure(player.user)

    return stats


def _upsert_session_stats(session, stats_by_uid):
    """Write / overwrite PlayerSessionStat rows for this session."""
    for uid, s in stats_by_uid.items():
        PlayerSessionStat.objects.update_or_create(
            session=session,
            user=s['user'],
            defaults={
                'runs':          s['runs'],
                'balls_faced':   s['balls_faced'],
                'wickets':       s['wickets'],
                'balls_bowled':  s['balls_bowled'],
                'runs_conceded': s['runs_conceded'],
                'catches':       s['catches'],
                'stumpings':     s['stumpings'],
            },
        )


# ── Rating formula ───────────────────────────────────────────────────────────

def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


def _batting_raw(stat):
    """0–5 raw score from a single session's batting stat row. None = skip."""
    if stat.balls_faced == 0:
        return None
    sr = (stat.runs / stat.balls_faced) * 100
    return _clamp(sr / 30.0, 0, 5)   # SR 150 → 5.0


def _bowling_raw(stat):
    """0–5 raw score (lower economy = higher). None = skip."""
    if stat.balls_bowled == 0:
        return None
    economy = (stat.runs_conceded / stat.balls_bowled) * 6
    # eco 1 → 5, eco 6 → 0, eco 7+ → clamped 0
    return _clamp(6 - economy, 0, 5)


def _fielding_raw(stat):
    """0–5 raw score from catches + stumpings in one session."""
    return _clamp((stat.catches + stat.stumpings) * 1.25, 0, 5)


def _weighted_average(values_newest_first):
    """Rank-based weighted average. weights: newest = N, oldest = 1.
    Skips None values (player didn't bat/bowl that session).
    Returns None if no valid values."""
    # Filter out None
    valid = [(i, v) for i, v in enumerate(
        values_newest_first) if v is not None]
    if not valid:
        return None
    n = len(valid)
    total_weight = 0
    weighted_sum = 0.0
    for rank, (original_index, value) in enumerate(valid):
        # newest valid = highest weight
        weight = n - rank
        weighted_sum += weight * value
        total_weight += weight
    return weighted_sum / total_weight


def _recalculate_ratings(user):
    """Recompute and save the three ratings on user from their full history."""
    # Fetch all stat rows ordered newest session first
    stat_rows = list(
        PlayerSessionStat.objects
        .filter(user=user)
        .select_related('session')
        .order_by('-session__date', '-session__id')
    )

    batting_avg = _weighted_average([_batting_raw(s) for s in stat_rows])
    bowling_avg = _weighted_average([_bowling_raw(s) for s in stat_rows])
    fielding_avg = _weighted_average([_fielding_raw(s) for s in stat_rows])

    def _to_decimal(val):
        """Convert float → Decimal(x.x), 0 if None (no history)."""
        if val is None:
            return Decimal('0.0')
        return Decimal(str(round(val, 1))).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

    user.batting_rating = _to_decimal(batting_avg)
    user.bowling_rating = _to_decimal(bowling_avg)
    user.fielding_rating = _to_decimal(fielding_avg)
    user.save(update_fields=['batting_rating',
              'bowling_rating', 'fielding_rating'])


# ── Public entry point ───────────────────────────────────────────────────────

@transaction.atomic
def compute_session_ratings(session):
    """Compute PlayerSessionStat rows for *session*, then recalculate ratings
    for every user who appeared. Returns the number of users updated."""

    stats_by_uid = _collect_session_stats(session)
    if not stats_by_uid:
        return 0

    _upsert_session_stats(session, stats_by_uid)

    for s in stats_by_uid.values():
        _recalculate_ratings(s['user'])

    return len(stats_by_uid)
