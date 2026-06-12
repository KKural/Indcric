"""Check player ratings and simulate balanced team split.

Run with live DB env var set to see real ratings, or without to use local data.

Usage:
    python -m kural.check_ratings
    python -m kural.check_ratings --session 20   # split based on who attended session 20
"""
from django.contrib.auth import get_user_model
from decimal import Decimal
import os
import sys
import django
import argparse
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cric_core.settings')
django.setup()

User = get_user_model()


# ── Team balancing algorithm (mirrors what the app does) ─────────────────────

def combined_rating(u):
    bat = float(u.batting_rating or 2.5)
    bowl = float(u.bowling_rating or 2.5)
    fld = float(u.fielding_rating or 2.5)
    return round((bat + bowl + fld) / 3, 2)


def balance_teams(players):
    """Greedy snake-draft split: sort by rating desc, alternate A/B/B/A/A/B..."""
    sorted_players = sorted(
        players, key=lambda u: combined_rating(u), reverse=True)
    team_a, team_b = [], []
    for i, p in enumerate(sorted_players):
        # Snake draft: 0→A, 1→B, 2→B, 3→A, 4→A, 5→B ...
        slot = i % 4
        if slot in (0, 3):
            team_a.append(p)
        else:
            team_b.append(p)
    return team_a, team_b


def team_stats(players):
    ratings = [combined_rating(p) for p in players]
    return {
        'total': round(sum(ratings), 2),
        'avg':   round(sum(ratings) / len(ratings), 2) if ratings else 0,
        'min':   round(min(ratings), 2) if ratings else 0,
        'max':   round(max(ratings), 2) if ratings else 0,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument('--session', type=int, default=None,
                    help='Use players from a specific session ID')
args = parser.parse_args()

print("\n" + "="*65)
print("PLAYER RATINGS (from DB)")
print("="*65)
print(f"{'Username':<25} {'Batting':>7} {'Bowling':>7} {'Fielding':>8} {'Combined':>9}")
print("-"*65)

if args.session:
    from apps.sessions.models import SessionPlayer
    session_players = (
        SessionPlayer.objects.filter(session_id=args.session)
        .select_related('user')
        .order_by('-user__batting_rating')
    )
    players = [sp.user for sp in session_players]
    print(
        f"  (Filtered to session id={args.session} — {len(players)} players)\n")
else:
    players = list(
        User.objects.filter(is_active=True)
        .exclude(username__startswith='test_')
        .exclude(username__startswith='Un_registered')
        .order_by('-batting_rating')
    )

for u in players:
    bat = float(u.batting_rating or 0)
    bowl = float(u.bowling_rating or 0)
    fld = float(u.fielding_rating or 0)
    comb = combined_rating(u)
    name = u.get_full_name() or u.username
    print(f"  {name:<23} {bat:>7.1f} {bowl:>7.1f} {fld:>8.1f} {comb:>9.2f}")

# ── Check conditions ──────────────────────────────────────────────────────────
print("\n" + "="*65)
print("CONDITIONS CHECK")
print("="*65)

all_rated = [u for u in players if any([
    u.batting_rating and u.batting_rating > 0,
    u.bowling_rating and u.bowling_rating > 0,
    u.fielding_rating and u.fielding_rating > 0,
])]
unrated = [u for u in players if u not in all_rated]

print(f"  Players with ratings:    {len(all_rated)}")
print(f"  Players with all zeros:  {len(unrated)}")
if unrated:
    names = ', '.join(u.get_full_name() or u.username for u in unrated)
    print(f"    → {names}")
    print(f"    ⚠ These players have no match history yet — rated 0.")

# ── Team split simulation ─────────────────────────────────────────────────────
split_pool = all_rated if all_rated else players

print("\n" + "="*65)
print(f"SIMULATED TEAM SPLIT ({len(split_pool)} players)")
print("="*65)

team_a, team_b = balance_teams(split_pool)
stats_a = team_stats(team_a)
stats_b = team_stats(team_b)
diff = abs(stats_a['avg'] - stats_b['avg'])

print(f"\n  Team A ({len(team_a)} players) — avg rating: {stats_a['avg']}")
for u in sorted(team_a, key=lambda u: combined_rating(u), reverse=True):
    print(f"    {u.get_full_name() or u.username:<25} combined={combined_rating(u):.2f}  bat={float(u.batting_rating or 0):.1f}  bowl={float(u.bowling_rating or 0):.1f}  fld={float(u.fielding_rating or 0):.1f}")

print(f"\n  Team B ({len(team_b)} players) — avg rating: {stats_b['avg']}")
for u in sorted(team_b, key=lambda u: combined_rating(u), reverse=True):
    print(f"    {u.get_full_name() or u.username:<25} combined={combined_rating(u):.2f}  bat={float(u.batting_rating or 0):.1f}  bowl={float(u.bowling_rating or 0):.1f}  fld={float(u.fielding_rating or 0):.1f}")

print(f"\n  {'─'*45}")
print(
    f"  Team A total: {stats_a['total']}  avg: {stats_a['avg']}  (min {stats_a['min']} / max {stats_a['max']})")
print(
    f"  Team B total: {stats_b['total']}  avg: {stats_b['avg']}  (min {stats_b['min']} / max {stats_b['max']})")
print(f"  Avg difference: {diff:.2f}")

if diff <= 0.3:
    print(f"  ✓ BALANCED — avg difference ≤ 0.3")
elif diff <= 0.5:
    print(f"  ~ ACCEPTABLE — avg difference ≤ 0.5 (minor imbalance)")
else:
    print(
        f"  ✗ IMBALANCED — avg difference {diff:.2f} > 0.5, consider manual adjustment")

print()
