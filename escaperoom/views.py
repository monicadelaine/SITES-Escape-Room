"""
Team-facing views: login, roster, play router, activity submission.
"""
import logging
import time
import traceback

from django.contrib.auth.hashers import check_password
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .graders import GRADER_REGISTRY, resolve_config
from .inputs import INPUT_REGISTRY
from .models import (
    Activity,
    AttemptLog,
    LLMMessage,
    Session,
    Team,
    TeamActivityProgress,
    TeamMember,
)

logger = logging.getLogger("escaperoom.attempts")

# ---------------------------------------------------------------------------
# Session / team helpers
# ---------------------------------------------------------------------------

RATE_LIMIT_SECONDS = 2  # min gap between submissions per team


def _get_session_or_404(slug):
    return get_object_or_404(Session, slug=slug, is_active=True)


def _get_team(request, session):
    team_id = request.session.get("team_id")
    session_id = request.session.get("session_id")
    if not team_id or session_id != session.id:
        return None
    try:
        return Team.objects.get(pk=team_id, session=session)
    except Team.DoesNotExist:
        return None


def _require_team(request, session):
    """Return (team, redirect_response).  If team is None, redirect to login."""
    team = _get_team(request, session)
    if team is None:
        return None, redirect("login", slug=session.slug)
    return team, None


def _current_activity(team):
    """
    Return the first activity that is not yet 'completed', or None if all done.
    Activities are ordered by Activity.order.
    """
    progress_qs = (
        TeamActivityProgress.objects
        .filter(team=team)
        .select_related("activity")
        .order_by("activity__order")
    )
    for p in progress_qs:
        if p.status != "completed":
            return p.activity, p
    return None, None


def _build_dial_states(team, current_activity=None):
    """Build the list of dial states for the door progress indicator."""
    progress_qs = (
        TeamActivityProgress.objects
        .filter(team=team)
        .select_related("activity")
        .order_by("activity__order")
    )
    states = []
    for p in progress_qs:
        if p.status == "completed":
            css = "done"
        elif current_activity and p.activity_id == current_activity.pk:
            css = "active"
        elif p.status == "in_progress":
            css = "active"
        else:
            css = ""
        states.append({"order": p.activity.order, "css_class": css})
    return states


def _unlock_next(team, completed_activity):
    """Mark the next locked activity as in_progress."""
    next_activities = Activity.objects.filter(
        session=team.session,
        order__gt=completed_activity.order,
    ).order_by("order")
    if next_activities.exists():
        next_act = next_activities.first()
        TeamActivityProgress.objects.filter(team=team, activity=next_act).update(
            status="in_progress",
            started_at=timezone.now(),
        )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def login_view(request, slug):
    session = _get_session_or_404(slug)
    error = None

    if request.method == "POST":
        team_name = request.POST.get("team_name", "").strip()
        password = request.POST.get("password", "")
        try:
            team = Team.objects.get(session=session, name=team_name)
            if check_password(password, team.password_hash):
                request.session["team_id"] = team.pk
                request.session["session_id"] = session.pk
                return redirect("roster", slug=slug)
            else:
                error = "Incorrect password."
        except Team.DoesNotExist:
            error = "Team not found."

    return render(request, "escaperoom/login.html", {
        "session": session,
        "error": error,
    })


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def roster_view(request, slug):
    session = _get_session_or_404(slug)
    team, redir = _require_team(request, session)
    if redir:
        return redir

    already_done = team.roster_completed_at is not None

    if request.method == "POST" and not already_done:
        names = [v.strip() for v in request.POST.getlist("name") if v.strip()]
        if names:
            # Clear any existing members (shouldn't exist, but be safe)
            team.members.all().delete()
            for i, name in enumerate(names):
                TeamMember.objects.create(team=team, name=name, order=i)
            team.roster_completed_at = timezone.now()
            team.save(update_fields=["roster_completed_at"])

            # Unlock the first activity
            first_act = Activity.objects.filter(session=session).order_by("order").first()
            if first_act:
                TeamActivityProgress.objects.filter(team=team, activity=first_act).update(
                    status="in_progress",
                    started_at=timezone.now(),
                )

            return redirect("play", slug=slug)

    members = list(team.members.order_by("order"))
    return render(request, "escaperoom/roster.html", {
        "session": session,
        "team": team,
        "members": members,
        "already_done": already_done,
    })


# ---------------------------------------------------------------------------
# Play router
# ---------------------------------------------------------------------------

def play_view(request, slug):
    session = _get_session_or_404(slug)
    team, redir = _require_team(request, session)
    if redir:
        return redir

    # Must complete roster first
    if not team.roster_completed_at:
        return redirect("roster", slug=slug)

    now = timezone.now()

    # Synced start: hold everyone at the waiting screen
    if session.start_time and now < session.start_time:
        return render(request, "escaperoom/waiting.html", {
            "session": session,
            "team": team,
            "start_time_iso": session.start_time.isoformat(),
        })

    # Check if session has ended
    session_ended = (
        not session.is_active
        or (session.end_time and now >= session.end_time)
    )

    activity, progress = _current_activity(team)

    if activity is None:
        # All doors completed
        members = list(team.members.order_by("order"))
        return render(request, "escaperoom/complete.html", {
            "session": session,
            "team": team,
            "members": members,
            "dial_states": _build_dial_states(team),
        })

    if session_ended:
        # Session over, team didn't finish
        all_activities = list(Activity.objects.filter(session=session).order_by("order"))
        progress_map = {
            p.activity_id: p
            for p in TeamActivityProgress.objects.filter(team=team)
        }
        activity_rows = [
            {
                "activity": act,
                "status": progress_map[act.pk].status if act.pk in progress_map else "locked",
            }
            for act in all_activities
        ]
        completed_count = sum(1 for r in activity_rows if r["status"] == "completed")
        return render(request, "escaperoom/timesup.html", {
            "session": session,
            "team": team,
            "completed_count": completed_count,
            "total": len(all_activities),
            "activity_rows": activity_rows,
            "dial_states": _build_dial_states(team),
        })

    # Pull last submission result from session flash
    last_result = request.session.pop("last_result", None)

    # Render the current activity
    input_handler = INPUT_REGISTRY[activity.input_type]()
    extra_ctx = input_handler.get_form_context(activity, team, progress)

    return render(request, input_handler.template_name, {
        "session": session,
        "team": team,
        "activity": activity,
        "progress": progress,
        "dial_states": _build_dial_states(team, activity),
        "last_result": last_result,
        **extra_ctx,
    })


# ---------------------------------------------------------------------------
# Activity submission
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
def submit_view(request, slug, activity_id):
    session = _get_session_or_404(slug)
    team, redir = _require_team(request, session)
    if redir:
        return redir

    activity = get_object_or_404(Activity, pk=activity_id, session=session)
    try:
        progress = TeamActivityProgress.objects.get(team=team, activity=activity)
    except TeamActivityProgress.DoesNotExist:
        return redirect("play", slug=slug)

    if progress.status == "completed":
        return redirect("play", slug=slug)

    # Rate-limit: check last attempt timestamp
    # Per-activity delay can be set via config["attempt_delay_seconds"] and increases each attempt.
    cfg = resolve_config(activity, team)
    base_delay = cfg.get("attempt_delay_seconds", None)
    if base_delay is not None:
        attempt_delay = base_delay * max(1, progress.attempts)
    else:
        attempt_delay = RATE_LIMIT_SECONDS

    last = (
        AttemptLog.objects
        .filter(team=team, activity=activity)
        .order_by("-submitted_at")
        .first()
    )
    if last:
        elapsed = (timezone.now() - last.submitted_at).total_seconds()
        if elapsed < attempt_delay:
            input_handler = INPUT_REGISTRY[activity.input_type]()
            extra_ctx = input_handler.get_form_context(activity, team, progress)
            return render(request, input_handler.template_name, {
                "session": session,
                "team": team,
                "activity": activity,
                "progress": progress,
                "rate_limited": True,
                "attempt_delay": int(attempt_delay),
                **extra_ctx,
            })

    input_handler = INPUT_REGISTRY[activity.input_type]()
    payload = input_handler.parse_submission(request)
    grader = GRADER_REGISTRY[activity.grader_type]

    passed = None
    detail = ""
    error_trace = ""
    extra = {}

    try:
        passed, detail, extra = grader(activity, team, payload)
    except Exception:
        error_trace = traceback.format_exc()
        detail = "Something went wrong — try again or flag a staff member."
        logger.error(
            "Grader exception: team=%s activity=%s\n%s",
            team.name, activity.title, error_trace,
        )

    progress.attempts += 1
    if progress.status == "locked":
        progress.status = "in_progress"
        progress.started_at = timezone.now()

    if passed is True:
        progress.status = "completed"
        progress.completed_at = timezone.now()

    progress.save()

    log = AttemptLog.objects.create(
        team=team,
        activity=activity,
        payload=payload,
        passed=passed,
        detail=detail,
        error_trace=error_trace,
    )

    logger.info(
        "Attempt: team=%s activity=%s passed=%s attempts=%d",
        team.name, activity.title, passed, progress.attempts,
    )

    if passed is True:
        _unlock_next(team, activity)

    # Redirect back to play (PRG pattern) — pass result via session flash
    request.session["last_result"] = {
        "passed": passed,
        "detail": detail,
        "decoded_text": extra.get("decoded_text"),
        "ciphertext": extra.get("ciphertext"),
        "slot_results": extra.get("slot_results"),   # match_pairs per-row feedback
        "last_match": extra.get("last_match"),        # match_pairs previous answers
        "activity_id": activity.pk,
    }
    return redirect("play", slug=slug)


# ---------------------------------------------------------------------------
# LLM chat message (AJAX POST)
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
def chat_send_view(request, slug, activity_id):
    session = _get_session_or_404(slug)
    team, redir = _require_team(request, session)
    if redir:
        return JsonResponse({"error": "Not logged in"}, status=403)

    activity = get_object_or_404(Activity, pk=activity_id, session=session)
    progress = get_object_or_404(TeamActivityProgress, team=team, activity=activity)

    if progress.status == "completed":
        return JsonResponse({"error": "Already completed"}, status=400)

    message = request.POST.get("message", "").strip()
    if not message:
        return JsonResponse({"error": "Empty message"}, status=400)

    # Length cap (cheap block of copy-paste jailbreak walls)
    MAX_LEN = 500
    if len(message) > MAX_LEN:
        LLMMessage.objects.create(
            team=team, activity=activity,
            role="user", content=message, blocked=True,
        )
        return JsonResponse({"error": f"Message too long (max {MAX_LEN} chars)."}, status=400)

    # Rate-limit: 1 message per 2 seconds per team
    last_msg = LLMMessage.objects.filter(
        team=team, activity=activity, role="user"
    ).order_by("-created_at").first()
    if last_msg:
        elapsed = (timezone.now() - last_msg.created_at).total_seconds()
        if elapsed < 2:
            return JsonResponse({"error": "Slow down — wait a moment before sending again."}, status=429)

    # Hard cap on total messages
    total_turns = LLMMessage.objects.filter(team=team, activity=activity).count()
    if total_turns >= 60:
        return JsonResponse({"error": "Message limit reached for this door."}, status=429)

    # Profanity / safety pre-check (simple keyword list)
    _BLOCKED_KEYWORDS = [
        "fuck", "shit", "ass", "bitch", "nigga", "nigger", "cunt",
    ]
    lower_msg = message.lower()
    if any(kw in lower_msg for kw in _BLOCKED_KEYWORDS):
        LLMMessage.objects.create(
            team=team, activity=activity,
            role="user", content=message, blocked=True,
        )
        return JsonResponse({"error": "Message blocked by content filter."}, status=400)

    # Save user message
    LLMMessage.objects.create(
        team=team, activity=activity,
        role="user", content=message, blocked=False,
    )

    # Call Gemini
    from django.conf import settings as django_settings

    cfg = resolve_config(activity, team)
    system_prompt = cfg.get("system_prompt_template", "").format(
        secret=cfg.get("secret", "")
    )
    

    reply_text = _call_gemini(
        api_key=django_settings.GEMINI_API_KEY,
        system_prompt=system_prompt,
        team=team,
        activity=activity,
    )

    # Save model reply
    LLMMessage.objects.create(
        team=team, activity=activity,
        role="model", content=reply_text, blocked=False,
    )

    return JsonResponse({"reply": reply_text})


def _call_gemini(api_key, system_prompt, team, activity):
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Pick the newest available Flash-tier model
        model_name = "gemini-2.5-flash"
        try:
            available = [m.name for m in client.models.list()]
            flash_models = [m for m in available if "flash" in m.lower()]
            if flash_models:
                model_name = flash_models[0].replace("models/", "")
        except Exception:
            pass

        all_msgs = list(
            LLMMessage.objects.filter(team=team, activity=activity, blocked=False)
            .order_by("created_at")
        )

        if not all_msgs or all_msgs[-1].role != "user":
            return "I'm here. What would you like to know?"

        contents = [
            types.Content(role=msg.role, parts=[types.Part(text=msg.content)])
            for msg in all_msgs
        ]

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return response.text

    except Exception as exc:
        logger.error("Gemini API error: %s", exc, exc_info=True)
        return "The guardian seems distracted. Try again in a moment."
