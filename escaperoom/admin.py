from django.contrib import admin

from .models import (
    Activity,
    AttemptLog,
    LLMMessage,
    MessagePool,
    Session,
    SessionAuditLog,
    Team,
    TeamActivityProgress,
    TeamMember,
)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "start_time", "end_time", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "session", "roster_completed_at"]
    list_filter = ["session"]
    search_fields = ["name"]


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ["name", "team", "order"]
    list_filter = ["team__session"]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "session", "order", "input_type", "grader_type"]
    list_filter = ["session", "input_type", "grader_type"]


@admin.register(TeamActivityProgress)
class TeamActivityProgressAdmin(admin.ModelAdmin):
    list_display = ["team", "activity", "status", "attempts", "started_at", "completed_at"]
    list_filter = ["status", "activity__session"]


@admin.register(AttemptLog)
class AttemptLogAdmin(admin.ModelAdmin):
    list_display = ["team", "activity", "submitted_at", "passed", "manual_override"]
    list_filter = ["passed", "manual_override", "activity__session"]
    readonly_fields = ["submitted_at", "error_trace"]


@admin.register(LLMMessage)
class LLMMessageAdmin(admin.ModelAdmin):
    list_display = ["team", "activity", "role", "blocked", "created_at", "short_content"]
    list_filter = ["role", "blocked", "activity__session"]

    @admin.display(description="Content")
    def short_content(self, obj):
        return obj.content[:80]


@admin.register(MessagePool)
class MessagePoolAdmin(admin.ModelAdmin):
    list_display = ["pool_type", "value", "times_used", "last_used_at"]
    list_filter = ["pool_type"]


@admin.register(SessionAuditLog)
class SessionAuditLogAdmin(admin.ModelAdmin):
    list_display = ["session", "action", "staff_user", "created_at", "detail"]
    list_filter = ["action", "session"]
    readonly_fields = ["created_at"]
