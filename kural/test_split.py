"""Test team split for the specific players in the current session screenshot.

Players: ashok_kumar, bhanu, mani_kaarthik, Niranjan, Sathish, tc,
         Koushal_kumar, PremKRaghupathi, Ramuhaky, Shobin, Akhil_Reddy, Aru, kuralarasan
"""
from django.contrib.auth import get_user_model
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cric_core.settings')
django.setup()

User = get_user_model()

# IDs from players.md
PLAYER_IDS = [31, 1, 60, 28, 43, 49, 41, 22, 30, 48, 15, 35, 14]

players = list(
    User.objects.filter(id__in=PLAYER_IDS)
    .order_by('first_name', 'username')  # A–Z
)


def combined_rating(u):
    bat = float(u.batting_rating or 2.5)
    bowl = float(u.bowling_rating or 2.5)
    fld = float(u.fielding_rating or 2.5)
    return round((bat + bowl + fld) / 3, 2)


def balance_teams(players):
    """Snake-draft: sort desc by rating, alternate A/B/B/A/A/B/B/A..."""
    sorted_p = sorted(players, key=lambda u: combined_rating(u), reverse=True)
    team_a, team_b = [], []
    for i, p in enumerate(sorted_p):
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
    }


print("\n" + "="*65)
print("PLAYER RATINGS (A–Z)")
print("="*65)
print(f"  {'Name':<28} {'Bat':>4} {'Bowl':>5} {'Fld':>5} {'Comb':>6}")
print("  " + "─"*52)
for u in players:
    name = u.get_full_name() or u.username
    bat = float(u.batting_rating or 0)
    bowl = float(u.bowling_rating or 0)
    fld = float(u.fielding_rating or 0)
    comb = combined_rating(u)
    flag = "  ← no history (2.5 default)" if bat == bowl == fld == 2.5 else ""
    flag2 = "  ← played, no bat/bowl (0)" if bat == bowl == 0 and fld == 0 else ""
    print(
        f"  {name:<28} {bat:>4.1f} {bowl:>5.1f} {fld:>5.1f} {comb:>6.2f}{flag}{flag2}")

print("\n" + "="*65)
print("BALANCED TEAM SPLIT")
print("="*65)

team_a, team_b = balance_teams(players)
stats_a = team_stats(team_a)
stats_b = team_stats(team_b)
diff = abs(stats_a['avg'] - stats_b['avg'])

print(f"\n  Team A ({len(team_a)} players) — avg: {stats_a['avg']}")
for u in sorted(team_a, key=lambda u: combined_rating(u), reverse=True):
    name = u.get_full_name() or u.username
    print(f"    {name:<28} {combined_rating(u):.2f}")

print(f"\n  Team B ({len(team_b)} players) — avg: {stats_b['avg']}")
for u in sorted(team_b, key=lambda u: combined_rating(u), reverse=True):
    name = u.get_full_name() or u.username
    print(f"    {name:<28} {combined_rating(u):.2f}")

print(f"\n  Avg difference: {diff:.2f}")
if diff <= 0.3:
    print(f"  ✓ BALANCED")
elif diff <= 0.5:
    print(f"  ~ ACCEPTABLE (minor imbalance)")
else:
    print(f"  ✗ IMBALANCED — consider swapping players manually")
print()
