"""
seed_sample_polls.py
--------------------
Creates 3 sample weekly sessions with Yes/No attendance polls.

Each week:  15 players vote  →  12 Yes + 3 No  (different mix each week)
After seeding, the greedy team-split result is printed for each week.

Usage:
    python manage.py seed_sample_polls

Pass --clear to wipe previously seeded sessions before re-running.
"""

import datetime
import random
from django.core.management.base import BaseCommand
from cric.models import User, Session, Poll, Vote


# ---------------------------------------------------------------------------
# Player roster — 18 players so each week can have a slightly different 15
# ---------------------------------------------------------------------------
PLAYER_DATA = [
    {"username": "arjun_k",    "first_name": "Arjun",    "last_name": "Kumar",
        "role": "batsman",    "batting": 8.5, "bowling": 4.0, "fielding": 7.0},
    {"username": "ravi_s",     "first_name": "Ravi",     "last_name": "Sharma",
        "role": "bowler",     "batting": 4.0, "bowling": 8.5, "fielding": 6.5},
    {"username": "karan_m",    "first_name": "Karan",    "last_name": "Mehta",
        "role": "allrounder", "batting": 7.0, "bowling": 7.0, "fielding": 7.0},
    {"username": "vijay_p",    "first_name": "Vijay",    "last_name": "Patel",
        "role": "batsman",    "batting": 7.5, "bowling": 3.5, "fielding": 6.0},
    {"username": "suresh_n",   "first_name": "Suresh",   "last_name": "Nair",
        "role": "bowler",     "batting": 3.5, "bowling": 7.5, "fielding": 5.5},
    {"username": "deepak_r",   "first_name": "Deepak",   "last_name": "Rao",
        "role": "allrounder", "batting": 6.5, "bowling": 6.5, "fielding": 6.0},
    {"username": "amit_v",     "first_name": "Amit",     "last_name": "Verma",
        "role": "batsman",    "batting": 9.0, "bowling": 3.0, "fielding": 7.5},
    {"username": "sanjay_g",   "first_name": "Sanjay",   "last_name": "Gupta",
        "role": "bowler",     "batting": 3.0, "bowling": 9.0, "fielding": 5.0},
    {"username": "rahul_j",    "first_name": "Rahul",    "last_name": "Joshi",
        "role": "allrounder", "batting": 7.5, "bowling": 7.5, "fielding": 7.5},
    {"username": "nikhil_c",   "first_name": "Nikhil",   "last_name": "Chopra",
        "role": "batsman",    "batting": 6.0, "bowling": 4.0, "fielding": 8.0},
    {"username": "priya_t",    "first_name": "Priya",    "last_name": "Tiwari",
        "role": "bowler",     "batting": 4.5, "bowling": 8.0, "fielding": 6.0},
    {"username": "rohan_b",    "first_name": "Rohan",    "last_name": "Bose",
        "role": "allrounder", "batting": 6.0, "bowling": 6.0, "fielding": 6.5},
    {"username": "anil_d",     "first_name": "Anil",     "last_name": "Desai",
        "role": "batsman",    "batting": 5.5, "bowling": 3.0, "fielding": 7.0},
    {"username": "kartik_s",   "first_name": "Kartik",   "last_name": "Singh",
        "role": "bowler",     "batting": 3.5, "bowling": 7.0, "fielding": 5.0},
    {"username": "manish_y",   "first_name": "Manish",   "last_name": "Yadav",
        "role": "allrounder", "batting": 6.5, "bowling": 5.5, "fielding": 6.0},
    {"username": "varun_m",    "first_name": "Varun",    "last_name": "Mishra",
        "role": "batsman",    "batting": 8.0, "bowling": 2.5, "fielding": 7.0},
    {"username": "tushar_k",   "first_name": "Tushar",   "last_name": "Kapoor",
        "role": "bowler",     "batting": 2.5, "bowling": 8.0, "fielding": 5.5},
    {"username": "gaurav_a",   "first_name": "Gaurav",   "last_name": "Aggarwal",
        "role": "allrounder", "batting": 5.5, "bowling": 5.5, "fielding": 7.0},
]

SESSIONS = [
    {"name": "Sample Week 1", "date": datetime.date(2026, 4, 6)},
    {"name": "Sample Week 2", "date": datetime.date(2026, 4, 13)},
    {"name": "Sample Week 3", "date": datetime.date(2026, 4, 20)},
]

# Each week uses a different 15 out of 18 (rotate the 3 who sit out)
# Week 1: skip indices 15,16,17  Week 2: skip 12,13,14  Week 3: skip 0,1,2
WEEK_ABSENT_INDICES = [
    {15, 16, 17},   # Week 1
    {12, 13, 14},   # Week 2
    {0, 1, 2},      # Week 3
]

# For each week: which of the 15 active players vote 'no' (0-based index in that week's list)
WEEK_NO_INDICES = [
    {2, 7, 12},   # Week 1
    {0, 5, 11},   # Week 2
    {3, 9, 14},   # Week 3
]


def greedy_split(yes_voters):
    """Replicate the app's greedy balanced-split algorithm."""
    players = sorted(
        yes_voters,
        key=lambda u: float(u.batting_rating +
                            u.bowling_rating + u.fielding_rating),
        reverse=True
    )
    team_a, team_b = [], []
    score_a, score_b = 0.0, 0.0
    for p in players:
        total = float(p.batting_rating + p.bowling_rating + p.fielding_rating)
        name = p.get_full_name() or p.username
        if score_a <= score_b:
            team_a.append((name, round(total, 1)))
            score_a += total
        else:
            team_b.append((name, round(total, 1)))
            score_b += total
    return team_a, score_a, team_b, score_b


class Command(BaseCommand):
    help = "Seed 3 weekly sample sessions with Yes/No polls and test team split"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete previously seeded sample sessions before re-running'
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted, _ = Session.objects.filter(
                name__startswith='Sample Week').delete()
            self.stdout.write(self.style.WARNING(
                f"Cleared {deleted} previously seeded session(s)."))

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR(
                "No superuser found. Create one with 'createsuperuser' first."))
            return

        # ── 1. Ensure all 18 sample players exist ──────────────────────────
        players = []
        for pd in PLAYER_DATA:
            user, created = User.objects.get_or_create(
                username=pd["username"],
                defaults={
                    "first_name": pd["first_name"],
                    "last_name":  pd["last_name"],
                    "role":       pd["role"],
                    "batting_rating":  pd["batting"],
                    "bowling_rating":  pd["bowling"],
                    "fielding_rating": pd["fielding"],
                }
            )
            if not created:
                # Update ratings in case they changed
                user.batting_rating = pd["batting"]
                user.bowling_rating = pd["bowling"]
                user.fielding_rating = pd["fielding"]
                user.role = pd["role"]
                user.save()
            players.append(user)
            tag = "created" if created else "updated"
            self.stdout.write(
                f"  {tag}: {user.get_full_name()} ({user.username})")

        self.stdout.write("")

        # ── 2. Create 3 sessions + polls + votes ───────────────────────────
        for week_idx, sess_data in enumerate(SESSIONS):
            absent = WEEK_ABSENT_INDICES[week_idx]
            no_set = WEEK_NO_INDICES[week_idx]

            active_players = [
                p for i, p in enumerate(players) if i not in absent
            ]  # 15 players

            session, _ = Session.objects.get_or_create(
                name=sess_data["name"],
                defaults={
                    "date":     sess_data["date"],
                    "time":     datetime.time(10, 0),
                    "location": "ICG Ground",
                    "duration": 3.0,
                    "cost":     0.0,
                    "created_by": admin,
                }
            )

            poll, _ = Poll.objects.get_or_create(
                session=session,
                defaults={"question": "Can you play this week?",
                          "is_open": False}
            )
            # Clear old votes if session already existed
            poll.votes.all().delete()

            yes_voters = []
            for local_idx, player in enumerate(active_players):
                choice = 'no' if local_idx in no_set else 'yes'
                Vote.objects.create(poll=poll, user=player, choice=choice)
                if choice == 'yes':
                    yes_voters.append(player)

            yes_count = len(yes_voters)
            no_count = len(active_players) - yes_count

            self.stdout.write(self.style.SUCCESS(
                f"── {sess_data['name']} ({sess_data['date']}) ──"
            ))
            self.stdout.write(
                f"   Players polled: {len(active_players)}  |  "
                f"Yes: {yes_count}  |  No: {no_count}"
            )
            self.stdout.write("   Absent this week: " + ", ".join(
                players[i].get_full_name() for i in sorted(absent)
            ))
            self.stdout.write("   No votes: " + ", ".join(
                active_players[i].get_full_name() for i in sorted(no_set)
            ))

            # ── 3. Run and display greedy split ────────────────────────────
            team_a, score_a, team_b, score_b = greedy_split(yes_voters)

            self.stdout.write("")
            self.stdout.write("   TEAM SPLIT (greedy balanced):")

            col_width = 32
            header = f"   {'Team A':<{col_width}} {'Team B':<{col_width}}"
            self.stdout.write(header)
            self.stdout.write("   " + "-" * (col_width * 2))

            for i in range(max(len(team_a), len(team_b))):
                a_str = f"{team_a[i][0]} ({team_a[i][1]})" if i < len(
                    team_a) else ""
                b_str = f"{team_b[i][0]} ({team_b[i][1]})" if i < len(
                    team_b) else ""
                self.stdout.write(
                    f"   {a_str:<{col_width}} {b_str:<{col_width}}")

            self.stdout.write(
                f"   {'Total: ' + str(round(score_a, 1)):<{col_width}} "
                f"{'Total: ' + str(round(score_b, 1)):<{col_width}}"
            )
            diff = abs(score_a - score_b)
            self.stdout.write(
                f"   Score difference: {round(diff, 1)}  "
                f"({'balanced' if diff <= 5 else 'unbalanced'})"
            )
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS(
            "Done. Sessions visible at /sessions/ in the app."
        ))
