"""Management command to backfill player ratings from historical match data.

Usage:
    # Recalculate ratings from ALL past sessions that have match data:
    python manage.py update_ratings

    # Recalculate ratings for a single session by ID:
    python manage.py update_ratings --session 42

    # Dry-run: show which sessions would be processed, no writes:
    python manage.py update_ratings --dry-run
"""

from django.core.management.base import BaseCommand

from apps.sessions.models import Session
from apps.matches.rating_engine import compute_session_ratings


class Command(BaseCommand):
    help = "Backfill PlayerSessionStat rows and recalculate player ratings from match data."

    def add_arguments(self, parser):
        parser.add_argument(
            '--session', type=int, default=None,
            help='Process a single session by ID instead of all past sessions.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List the sessions that would be processed without writing anything.',
        )

    def handle(self, *args, **options):
        session_id = options['session']
        dry_run = options['dry_run']

        if session_id:
            sessions = Session.objects.filter(id=session_id)
            if not sessions.exists():
                self.stderr.write(self.style.ERROR(
                    f"Session {session_id} not found."))
                return
        else:
            # Only process sessions that actually have at least one match
            sessions = (
                Session.objects
                .filter(matches__isnull=False)
                .distinct()
                .order_by('date')
            )

        total = sessions.count()
        if total == 0:
            self.stdout.write(self.style.WARNING(
                "No sessions with match data found."))
            return

        self.stdout.write(f"Found {total} session(s) to process.")

        if dry_run:
            for s in sessions:
                self.stdout.write(
                    f"  [dry-run] Would process: [{s.id}] {s.name} ({s.date})")
            return

        total_players = 0
        for s in sessions:
            updated = compute_session_ratings(s)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  [{s.id}] {s.name} ({s.date}) — {updated} player(s) updated")
            )
            total_players += updated

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Processed {total} session(s), updated ratings for {total_players} player-session pair(s)."
        ))
