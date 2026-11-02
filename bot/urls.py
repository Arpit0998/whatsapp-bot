from django.urls import path

from . import views

urlpatterns = [
    path("", views.demo, name="demo"),
    path("webhook/", views.webhook, name="webhook"),
    path("api/chat/", views.api_chat, name="api_chat"),
    path("api/chat/reset/", views.api_reset, name="api_reset"),
]
