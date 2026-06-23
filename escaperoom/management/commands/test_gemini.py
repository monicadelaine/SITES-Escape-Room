"""
python manage.py test_gemini [--team TEAM_NAME] [--slug SLUG]

Sends a test message to Gemini using the real system prompt and secret
for the specified team's LLM activity, then prints the reply.
Useful for verifying the API key, model name, and guardian persona before
the event.

If --team / --slug are omitted, a quick connectivity check is run instead
(no DB lookup needed — just confirms the API key works).
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Test the Gemini API connection for Door 3."

    def add_arguments(self, parser):
        parser.add_argument("--slug", type=str, default=None,
                            help="Session slug (e.g. spring2026-am)")
        parser.add_argument("--team", type=str, default=None,
                            help="Team name to test (uses that team's secret)")
        parser.add_argument("--message", type=str,
                            default="Hello. What is your purpose?",
                            help="Message to send to the guardian.")

    def handle(self, *args, **options):
        from django.conf import settings

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise CommandError(
                "GEMINI_API_KEY is not set. Add it to your .env file."
            )

        self.stdout.write(f"API key: {api_key[:8]}…{api_key[-4:]}")

        # ---- resolve system prompt ----------------------------------------
        system_prompt = (
            "You are a helpful assistant. Respond briefly."
        )
        secret_display = "(no secret — quick connectivity check)"

        if options["slug"] and options["team"]:
            from escaperoom.models import Activity, Session, Team, TeamActivityProgress
            from escaperoom.graders import resolve_config

            try:
                session = Session.objects.get(slug=options["slug"])
            except Session.DoesNotExist:
                raise CommandError(f"Session '{options['slug']}' not found.")

            try:
                team = Team.objects.get(session=session, name=options["team"])
            except Team.DoesNotExist:
                raise CommandError(f"Team '{options['team']}' not found in session '{options['slug']}'.")

            activity = Activity.objects.filter(
                session=session, grader_type="secret_match"
            ).order_by("order").first()
            if not activity:
                raise CommandError("No LLM activity (grader_type=secret_match) found in this session.")

            cfg = resolve_config(activity, team)
            secret = cfg.get("secret", "????")
            secret_display = secret
            system_prompt = cfg.get("system_prompt_template", "").format(secret=secret)
            self.stdout.write(f"Session : {session.name}")
            self.stdout.write(f"Team    : {team.name}")
            self.stdout.write(f"Secret  : {secret}")
            self.stdout.write(f"Activity: {activity.title}")
        else:
            self.stdout.write("(No --slug/--team given — running quick connectivity check)")

        self.stdout.write(f"\nSystem prompt:\n  {system_prompt[:200]}{'…' if len(system_prompt) > 200 else ''}")
        self.stdout.write(f"\nSending: \"{options['message']}\"")
        self.stdout.write("-" * 60)

        # ---- call Gemini ---------------------------------------------------
        try:
            import google.generativeai as genai
        except ImportError:
            raise CommandError(
                "google-generativeai is not installed. Run: pip install google-generativeai"
            )

        genai.configure(api_key=api_key)

        # List available models so we can confirm the right one is accessible
        try:
            available = [
                m.name for m in genai.list_models()
                if "generateContent" in m.supported_generation_methods
            ]
            flash_models = [m for m in available if "flash" in m.lower()]
            self.stdout.write(f"Flash-tier models available: {flash_models or '(none found)'}")
            model_name = flash_models[0].replace("models/", "") if flash_models else "gemini-1.5-flash"
        except Exception as e:
            self.stdout.write(f"Could not list models ({e}) — defaulting to gemini-1.5-flash")
            model_name = "gemini-1.5-flash"

        self.stdout.write(f"Using model: {model_name}\n")

        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt,
            )
            response = model.generate_content(options["message"])
            reply = response.text
        except Exception as exc:
            raise CommandError(f"Gemini API error: {exc}")

        self.stdout.write(f"Guardian reply:\n  {reply}")
        self.stdout.write("-" * 60)
        self.stdout.write(self.style.SUCCESS("Gemini connection OK."))
