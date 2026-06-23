"""
Staff admin views — gated by @staff_member_required.
All times displayed and accepted in America/Chicago (Central).
"""
import traceback
from zoneinfo import ZoneInfo

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

CENTRAL = ZoneInfo("America/Chicago")


def _to_central(dt):
    """Convert an aware UTC datetime to Central for display."""
    if dt is None:
        return None
    return dt.astimezone(CENTRAL)


def _fmt_central(dt):
    """'10:45 AM CT' string, or empty string if None."""
    if dt is None:
        return ""
    return _to_central(dt).strftime("%-I:%M %p CT")

from .models import (
    Activity,
    AttemptLog,
    LLMMessage,
    MessagePool,
    Session,
    SessionAuditLog,
    Team,
    TeamActivityProgress,
)
from .views_status import _build_grid


@staff_member_required(login_url="/admin/login/")
def manage_view(request, slug):
    session = get_object_or_404(Session, slug=slug)
    activities = list(Activity.objects.filter(session=session).order_by("order"))
    teams = list(Team.objects.filter(session=session).order_by("name"))
    rows = _build_grid(teams, activities)
    audit = list(session.audit_log.select_related("staff_user")[:20])

    now_central = _to_central(timezone.now())

    # Pre-fill the datetime-local input: value must be "YYYY-MM-DDTHH:MM" in Central
    end_time_central = _to_central(session.end_time)
    end_time_input_value = (
        end_time_central.strftime("%Y-%m-%dT%H:%M") if end_time_central else ""
    )

    return render(request, "escaperoom/manage.html", {
        "session": session,
        "activities": activities,
        "rows": rows,
        "audit": audit,
        "now_central": now_central,
        "end_time_display": _fmt_central(session.end_time),
        "end_time_input_value": end_time_input_value,
    })


@staff_member_required(login_url="/admin/login/")
def manage_detail_view(request, slug, team_id, activity_id):
    session = get_object_or_404(Session, slug=slug)
    team = get_object_or_404(Team, pk=team_id, session=session)
    activity = get_object_or_404(Activity, pk=activity_id, session=session)
    progress = get_object_or_404(TeamActivityProgress, team=team, activity=activity)
    attempts = list(AttemptLog.objects.filter(team=team, activity=activity).order_by("submitted_at"))

    chat_messages = None
    if activity.input_type == "chat_plus_secret":
        chat_messages = list(LLMMessage.objects.filter(team=team, activity=activity).order_by("created_at"))

    from .graders import resolve_config
    effective_cfg = resolve_config(activity, team)

    return render(request, "escaperoom/manage_detail.html", {
        "session": session,
        "team": team,
        "activity": activity,
        "progress": progress,
        "attempts": attempts,
        "chat_messages": chat_messages,
        "effective_cfg": effective_cfg,
    })


@staff_member_required(login_url="/admin/login/")
@require_POST
def manage_advance_to(request, slug, team_id, activity_id):
    """
    Testing helper: mark every door *before* this one as completed and
    set this door to in_progress, so the team lands here on next play load.
    Also ensures roster_completed_at is set so the team isn't stuck on roster.
    """
    session = get_object_or_404(Session, slug=slug)
    team = get_object_or_404(Team, pk=team_id, session=session)
    activity = get_object_or_404(Activity, pk=activity_id, session=session)

    now = timezone.now()

    # Complete all earlier doors
    prev_activities = Activity.objects.filter(session=session, order__lt=activity.order)
    for prev_act in prev_activities:
        TeamActivityProgress.objects.filter(team=team, activity=prev_act).update(
            status="completed",
            completed_at=now,
        )

    # Unlock this door
    TeamActivityProgress.objects.filter(team=team, activity=activity).update(
        status="in_progress",
        started_at=now,
    )

    # Ensure the team can reach play (roster must be done)
    if not team.roster_completed_at:
        team.roster_completed_at = now
        team.save(update_fields=["roster_completed_at"])

    SessionAuditLog.objects.create(
        session=session,
        staff_user=request.user,
        action="advance_to",
        detail=f"{team.name} advanced to Door {activity.order}: {activity.title}",
    )

    return redirect("manage_detail", slug=slug, team_id=team_id, activity_id=activity_id)


@staff_member_required(login_url="/admin/login/")
@require_POST
def manage_accept_advance(request, slug, team_id, activity_id):
    """Accept & Advance: mark the activity completed for a team."""
    session = get_object_or_404(Session, slug=slug)
    team = get_object_or_404(Team, pk=team_id, session=session)
    activity = get_object_or_404(Activity, pk=activity_id, session=session)
    progress = get_object_or_404(TeamActivityProgress, team=team, activity=activity)

    now = timezone.now()
    progress.status = "completed"
    progress.completed_at = now
    progress.save()

    AttemptLog.objects.create(
        team=team,
        activity=activity,
        payload="[staff accept & advance]",
        passed=True,
        detail="Manually accepted by staff.",
        manual_override=True,
        staff_user=request.user,
    )

    # Unlock next
    from .views import _unlock_next
    _unlock_next(team, activity)

    return redirect("manage_detail", slug=slug, team_id=team_id, activity_id=activity_id)


@staff_member_required(login_url="/admin/login/")
@require_POST
def manage_regenerate(request, slug, team_id, activity_id):
    """Regenerate cipher or LLM puzzle for a team."""
    import random
    session = get_object_or_404(Session, slug=slug)
    team = get_object_or_404(Team, pk=team_id, session=session)
    activity = get_object_or_404(Activity, pk=activity_id, session=session)
    progress = get_object_or_404(TeamActivityProgress, team=team, activity=activity)

    regen_type = request.POST.get("regen_type", "")

    if activity.grader_type == "decode_compare":
        if regen_type == "new_plaintext":
            pool_entry = MessagePool.objects.filter(pool_type="cipher_message").order_by(
                "last_used_at", "times_used"
            ).first()
            if pool_entry:
                progress.config_override["plaintext"] = pool_entry.value
                pool_entry.last_used_at = timezone.now()
                pool_entry.times_used += 1
                pool_entry.save()
        else:
            # New random shift
            used_shifts = {0}
            progress.config_override["shift"] = _random_shift(used_shifts)

        # Reset attempts if requested
        if request.POST.get("reset_attempts"):
            progress.attempts = 0

        progress.save()

    elif activity.grader_type == "secret_match":
        pool_entry = MessagePool.objects.filter(pool_type="llm_secret").order_by(
            "last_used_at", "times_used"
        ).first()
        if pool_entry:
            progress.config_override["secret"] = pool_entry.value
            pool_entry.last_used_at = timezone.now()
            pool_entry.times_used += 1
            pool_entry.save()
        progress.save()

    return redirect("manage_detail", slug=slug, team_id=team_id, activity_id=activity_id)


def _random_shift(exclude):
    import random
    choices = [s for s in range(1, 26) if s not in exclude]
    return random.choice(choices) if choices else random.randint(1, 25)


@staff_member_required(login_url="/admin/login/")
@require_POST
def manage_extend_time(request, slug):
    session = get_object_or_404(Session, slug=slug)
    try:
        minutes = int(request.POST.get("minutes", 5))
    except ValueError:
        minutes = 5

    old_display = _fmt_central(session.end_time) or "none"
    now = timezone.now()

    if session.end_time:
        session.end_time = session.end_time + timezone.timedelta(minutes=minutes)
    else:
        session.end_time = now + timezone.timedelta(minutes=minutes)

    session.save(update_fields=["end_time"])

    new_display = _fmt_central(session.end_time)
    SessionAuditLog.objects.create(
        session=session,
        staff_user=request.user,
        action="extend_time",
        detail=f"end_time {old_display} → {new_display} (+{minutes} min)",
    )

    end_central = _to_central(session.end_time)
    return JsonResponse({
        "end_time": session.end_time.isoformat(),
        "end_time_display": new_display,
        "end_time_input_value": end_central.strftime("%Y-%m-%dT%H:%M"),
        "detail": f"+{minutes} min — new end time: {new_display}",
    })


@staff_member_required(login_url="/admin/login/")
@require_POST
def manage_set_time(request, slug):
    """Set end_time to an explicit Central-time value from a datetime-local input."""
    session = get_object_or_404(Session, slug=slug)

    raw = request.POST.get("end_time", "").strip()
    if not raw:
        return JsonResponse({"error": "No time provided."}, status=400)

    try:
        # datetime-local gives "YYYY-MM-DDTHH:MM" — treat as Central
        from datetime import datetime
        naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
        new_end = naive.replace(tzinfo=CENTRAL)
    except ValueError:
        return JsonResponse({"error": f"Could not parse '{raw}'."}, status=400)

    old_display = _fmt_central(session.end_time) or "none"
    session.end_time = new_end
    session.save(update_fields=["end_time"])

    new_display = _fmt_central(session.end_time)
    SessionAuditLog.objects.create(
        session=session,
        staff_user=request.user,
        action="set_time",
        detail=f"end_time {old_display} → {new_display} (direct set)",
    )

    end_central = _to_central(session.end_time)
    return JsonResponse({
        "end_time": session.end_time.isoformat(),
        "end_time_display": new_display,
        "end_time_input_value": end_central.strftime("%Y-%m-%dT%H:%M"),
        "detail": f"End time set to {new_display}",
    })


@staff_member_required(login_url="/admin/login/")
@require_POST
def manage_end_session(request, slug):
    session = get_object_or_404(Session, slug=slug)
    session.is_active = False
    session.save(update_fields=["is_active"])

    SessionAuditLog.objects.create(
        session=session,
        staff_user=request.user,
        action="end_session",
        detail="Session manually ended by staff.",
    )

    return redirect("manage", slug=slug)
