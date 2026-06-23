"""
python manage.py clone_session <slug> <new_slug> [--start-time ISO] [--end-time ISO]

Copies activities and teams into a fresh session with progress reset,
roster cleared, and pool-backed values re-rolled.
"""
import random

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime


class Command(BaseCommand):
    help = "Clone an existing session into a new session with fresh progress."

    def add_arguments(self, parser):
        parser.add_argument("slug", type=str, help="Existing session slug")
        parser.add_argument("new_slug", type=str, help="New session slug")
        parser.add_argument("--start-time", type=str, default=None)
        parser.add_argument("--end-time", type=str, default=None)
        parser.add_argument("--name", type=str, default=None)

    def handle(self, *args, **options):
        from escaperoom.models import (
            Activity,
            MessagePool,
            Session,
            Team,
            TeamActivityProgress,
        )
        from django.utils import timezone

        slug = options["slug"]
        new_slug = options["new_slug"]

        try:
            source = Session.objects.get(slug=slug)
        except Session.DoesNotExist:
            raise CommandError(f"Source session '{slug}' not found.")

        if Session.objects.filter(slug=new_slug).exists():
            raise CommandError(f"Session '{new_slug}' already exists.")

        start_time = parse_datetime(options["start_time"]) if options["start_time"] else None
        end_time = parse_datetime(options["end_time"]) if options["end_time"] else None

        new_session = Session.objects.create(
            name=options["name"] or f"{source.name} (clone)",
            slug=new_slug,
            start_time=start_time,
            end_time=end_time,
        )
        self.stdout.write(f"Created session: {new_slug}")

        source_teams = list(Team.objects.filter(session=source))
        source_activities = list(Activity.objects.filter(session=source).order_by("order"))

        # Clone teams (preserve name + password hash, reset roster)
        new_teams = {}
        for t in source_teams:
            new_team = Team.objects.create(
                session=new_session,
                name=t.name,
                password_hash=t.password_hash,
                roster_completed_at=None,
            )
            new_teams[t.name] = new_team
            self.stdout.write(f"  Team: {t.name}")

        # Clone activities
        used_shifts = set()
        now = timezone.now()

        for act in source_activities:
            new_act = Activity.objects.create(
                session=new_session,
                order=act.order,
                title=act.title,
                input_type=act.input_type,
                grader_type=act.grader_type,
                config=act.config,
            )
            self.stdout.write(f"  Activity {act.order}: {act.title}")

            for t in source_teams:
                new_team = new_teams[t.name]
                # Re-roll pool-backed values
                override = {}
                old_progress = TeamActivityProgress.objects.filter(
                    team=t, activity=act
                ).first()

                if act.grader_type == "decode_compare":
                    # New random shift
                    shift = _unique_shift(used_shifts)
                    used_shifts.add(shift)
                    override["shift"] = shift
                    # Keep plaintext from old override or activity config
                    old_plaintext = (
                        (old_progress.config_override.get("plaintext") if old_progress else None)
                        or act.config.get("plaintext")
                    )
                    if old_plaintext:
                        override["plaintext"] = old_plaintext
                    else:
                        msg = _pull_from_pool("cipher_message", now)
                        if msg:
                            override["plaintext"] = msg

                elif act.grader_type == "secret_match":
                    secret = _pull_from_pool("llm_secret", now)
                    if secret:
                        override["secret"] = secret

                TeamActivityProgress.objects.create(
                    team=new_team,
                    activity=new_act,
                    status="locked",
                    config_override=override,
                )

        self.stdout.write(self.style.SUCCESS(f"Cloned '{slug}' → '{new_slug}'."))


def _unique_shift(used):
    choices = [s for s in range(1, 26) if s not in used]
    if not choices:
        choices = list(range(1, 26))
    return random.choice(choices)


def _pull_from_pool(pool_type, now):
    from escaperoom.models import MessagePool
    entry = MessagePool.objects.filter(pool_type=pool_type).order_by("last_used_at", "id").first()
    if entry:
        entry.last_used_at = now
        entry.times_used += 1
        entry.save()
        return entry.value
    return None
