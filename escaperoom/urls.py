from django.urls import path

from . import views, views_admin, views_certificate, views_status


urlpatterns = [
    # Team-facing
    path("<slug:slug>/login/", views.login_view, name="login"),
    path("<slug:slug>/roster/", views.roster_view, name="roster"),
    path("<slug:slug>/play/", views.play_view, name="play"),
    path("<slug:slug>/submit/<int:activity_id>/", views.submit_view, name="submit"),
    path("<slug:slug>/chat/<int:activity_id>/", views.chat_send_view, name="chat_send"),
    path("<slug:slug>/certificate/", views_certificate.certificate_view, name="certificate"),

    # Public status
    path("<slug:slug>/status/", views_status.status_view, name="status"),
    path("<slug:slug>/status.json", views_status.status_json, name="status_json"),

    # Staff admin
    path("<slug:slug>/manage/", views_admin.manage_view, name="manage"),
    path(
        "<slug:slug>/manage/<int:team_id>/<int:activity_id>/",
        views_admin.manage_detail_view,
        name="manage_detail",
    ),
    path(
        "<slug:slug>/manage/<int:team_id>/<int:activity_id>/accept/",
        views_admin.manage_accept_advance,
        name="manage_accept",
    ),
    path(
        "<slug:slug>/manage/<int:team_id>/<int:activity_id>/advance-to/",
        views_admin.manage_advance_to,
        name="manage_advance_to",
    ),
    path(
        "<slug:slug>/manage/<int:team_id>/<int:activity_id>/regenerate/",
        views_admin.manage_regenerate,
        name="manage_regenerate",
    ),
    path("<slug:slug>/manage/extend-time/", views_admin.manage_extend_time, name="manage_extend"),
    path("<slug:slug>/manage/set-time/", views_admin.manage_set_time, name="manage_set_time"),
    path("<slug:slug>/manage/end-session/", views_admin.manage_end_session, name="manage_end"),
]
