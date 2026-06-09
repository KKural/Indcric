"""Seed command for testing the drinks rotation feature.

Creates:
  - 15 fake players (8 alcohol drinkers, 7 non-alcohol)
  - 8 past sessions (weekly, going back 8 weeks)
  - All 15 players attended all 8 sessions (satisfies the ≥5 grace period)
  - Drink round history spread across sessions so players have different
    last-paid dates — the next-payer algorithm can be verified
  - 1 upcoming session (next week) to test the live suggestion card

Usage:
    python manage.py seed_drinks_test            # create everything
    python manage.py seed_drinks_test --flush    # wipe test data first, then recreate

All test users have username format test_<name> and password 'testpass123'.
The test superuser is test_admin / testpass123.
"""

import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction


PLAYERS = [
    # (first_name, last_name, drink_preference, role)
    ("Arjun",   "Kumar",    "alcohol",     "batsman"),
    ("Bhanu",   "Prasad",   "alcohol",     "bowler"),
    ("Chetan",  "Sharma",   "alcohol",     "allrounder"),
    ("Deepak",  "Nair",     "alcohol",     "batsman"),
    ("Ezhil",   "Murugan",  "alcohol",     "bowler"),
    ("Farhan",  "Sheikh",   "alcohol",     "allrounder"),
    ("Ganesh",  "Iyer",     "alcohol",     "batsman"),
    ("Harish",  "Reddy",    "alcohol",     "bowler"),
    ("Imran",   "Khan",     "non_alcohol", "allrounder"),
    ("Jayesh",  "Patel",    "non_alcohol", "batsman"),
    ("Karthik", "Rajan",    "non_alcohol", "bowler"),
    ("Lokesh",  "Verma",    "non_alcohol", "allrounder"),
    ("Manoj",   "Singh",    "non_alcohol", "batsman"),
    ("Naveen",  "Thomas",   "non_alcohol", "bowler"),
    ("Om",      "Prakash",  "non_alcohol", "allrounder"),
]

# Who paid for drinks in which past session (0-indexed, 0=oldest session)
# Each tuple: (session_index, drink_type, player_first_name)
DRINK_HISTORY = [
    (0, "alcohol",     "Arjun"),
    (0, "non_alcohol", "Imran"),
    (1, "alcohol",     "Bhanu"),
    (1, "non_alcohol", "Jayesh"),
    (2, "alcohol",     "Chetan"),
    (2, "non_alcohol", "Karthik"),
    (3, "alcohol",     "Deepak"),
    (3, "non_alcohol", "Lokesh"),
    (4, "alcohol",     "Ezhil"),
    (4, "non_alcohol", "Manoj"),
    (5, "alcohol",     "Farhan"),
    (5, "non_alcohol", "Naveen"),
    # Sessions 6 and 7 have no drink records — so the algorithm will suggest
    # Ganesh (alcohol, never paid) and Om (non_alcohol, never paid) for
    # the upcoming session, which is the fairest choice.
]


class Command(BaseCommand):
    help = "Seed fake data to test the drinks rotation feature."

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete all test_* users and their sessions before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from apps.sessions.models import Session, SessionPlayer, Attendance
        from apps.polls.models import Poll, Vote
        from apps.payments.models import DrinkRound

        User = get_user_model()

        if options['flush']:
            deleted, _ = User.objects.filter(
                username__startswith='test_').delete()
            self.stdout.write(self.style.WARNING(
                f"Flushed {deleted} test user(s) and cascaded data."))

        today = timezone.now().date()

        # ── Create admin ──────────────────────────────────────────────────────
        admin, created = User.objects.get_or_create(
            username='test_admin',
            defaults={
                'first_name': 'Test', 'last_name': 'Admin',
                'email': 'test_admin@example.com',
                'is_staff': True, 'is_superuser': True,
            }
        )
        if created:
            admin.set_password('testpass123')
            admin.save()
            self.stdout.write(f"  Created admin: test_admin / testpass123")
        else:
            self.stdout.write(f"  Admin test_admin already exists, skipping.")

        # ── Create players ────────────────────────────────────────────────────
        users = {}
        for first, last, drink_pref, role in PLAYERS:
            uname = f"test_{first.lower()}"
            user, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    'first_name': first, 'last_name': last,
                    'email': f"{uname}@example.com",
                    'drink_preference': drink_pref,
                    'role': role,
                    'is_active': True,
                }
            )
            if not created:
                # Update drink_preference in case it changed
                user.drink_preference = drink_pref
                user.save(update_fields=['drink_preference'])
            else:
                user.set_password('testpass123')
                user.save()
            users[first] = user

        pref_counts = sum(1 for _, _, dp, _ in PLAYERS if dp == 'alcohol')
        self.stdout.write(
            self.style.SUCCESS(
                f"  {len(users)} players ready "
                f"({pref_counts} alcohol, {len(users)-pref_counts} non-alcohol)"
            )
        )

        # ── Create 8 past sessions + 1 upcoming ──────────────────────────────
        sessions = []
        for i in range(8):
            # Weekly sessions going back 8 weeks, always on a Tuesday
            days_back = (8 - i) * 7
            session_date = today - datetime.timedelta(days=days_back)
            session_name = f"[TEST] Tuesday Session {i + 1}"

            session, _ = Session.objects.get_or_create(
                name=session_name,
                defaults={
                    'date': session_date,
                    'time': datetime.time(18, 0),
                    'duration': 3,
                    'location': 'Test Ground',
                    'cost': 60,
                    'attendance_confirmed': True,
                    'created_by': admin,
                }
            )
            sessions.append(session)

            # Poll + all-yes votes
            poll, _ = Poll.objects.get_or_create(
                session=session,
                defaults={'question': 'Will you attend?', 'is_open': False}
            )
            for user in users.values():
                Vote.objects.get_or_create(
                    poll=poll, user=user, defaults={'choice': 'yes'})
                sp, _ = SessionPlayer.objects.get_or_create(
                    session=session, user=user)
                Attendance.objects.get_or_create(
                    match_player=sp, defaults={'attended': True})

        self.stdout.write(self.style.SUCCESS(
            f"  {len(sessions)} past sessions created with full attendance."))

        # ── Upcoming session (next Tuesday) ───────────────────────────────────
        next_session_date = today + \
            datetime.timedelta(days=(1 - today.weekday()) % 7 + 7)
        upcoming, _ = Session.objects.get_or_create(
            name="[TEST] Upcoming Tuesday Session",
            defaults={
                'date': next_session_date,
                'time': datetime.time(18, 0),
                'duration': 3,
                'location': 'Test Ground',
                'cost': 60,
                'attendance_confirmed': False,
                'created_by': admin,
            }
        )
        poll_up, _ = Poll.objects.get_or_create(
            session=upcoming,
            defaults={'question': 'Will you attend?', 'is_open': True}
        )
        for user in users.values():
            Vote.objects.get_or_create(
                poll=poll_up, user=user, defaults={'choice': 'yes'})
            SessionPlayer.objects.get_or_create(session=upcoming, user=user)

        self.stdout.write(self.style.SUCCESS(
            f"  Upcoming session on {next_session_date}."))

        # ── Drink round history ───────────────────────────────────────────────
        rounds_created = 0
        for session_idx, drink_type, first_name in DRINK_HISTORY:
            session = sessions[session_idx]
            payer = users[first_name]
            _, created = DrinkRound.objects.get_or_create(
                session=session,
                drink_type=drink_type,
                defaults={'payer': payer, 'recorded_by': admin}
            )
            if created:
                rounds_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"  {rounds_created} drink round history records created."))

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(
            "Seed complete! Here's what to expect:"))
        self.stdout.write("")
        self.stdout.write(
            "  All 15 players attended 8 sessions → all are eligible")
        self.stdout.write("  (grace period = 5 sessions).")
        self.stdout.write("")
        self.stdout.write("  Alcohol track — last paid:")
        alcohol_paid = {fn: sessions[si].date for si,
                        dt, fn in DRINK_HISTORY if dt == "alcohol"}
        for _, _, _, role in PLAYERS:
            pass
        for first, _, dp, _ in PLAYERS:
            if dp == "alcohol":
                last = alcohol_paid.get(first, "NEVER")
                arrow = " ← should be next" if first not in alcohol_paid else ""
                self.stdout.write(
                    f"    test_{first.lower():12s}  last paid: {last}{arrow}")
        self.stdout.write("")
        self.stdout.write("  Non-alcohol track — last paid:")
        non_paid = {fn: sessions[si].date for si, dt,
                    fn in DRINK_HISTORY if dt == "non_alcohol"}
        for first, _, dp, _ in PLAYERS:
            if dp == "non_alcohol":
                last = non_paid.get(first, "NEVER")
                arrow = " ← should be next" if first not in non_paid else ""
                self.stdout.write(
                    f"    test_{first.lower():12s}  last paid: {last}{arrow}")
        self.stdout.write("")
        self.stdout.write("  Login at http://127.0.0.1:8000/accounts/login/")
        self.stdout.write("  Admin:  test_admin   / testpass123")
        self.stdout.write(
            "  Player: test_arjun   / testpass123  (alcohol drinker)")
        self.stdout.write(
            "  Player: test_imran   / testpass123  (non-alcohol drinker)")
        self.stdout.write(self.style.SUCCESS("=" * 60))
