import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import ChatSession, Lead, Message

admin.site.site_header = "Autoveer WhatsApp Bot"
admin.site.site_title = "Autoveer Bot Admin"
admin.site.index_title = "Leads & conversations"


@admin.action(description="Download selected leads as CSV")
def export_csv(modeladmin, request, queryset):
    cols = ["ref", "created_at", "title", "status", "brand", "model_name", "vehicle_type", "service_type", "reg_no",
            "topic", "preferred_date", "branch", "name", "phone", "whatsapp", "channel", "notes"]
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="autoveer-leads.csv"'
    resp.write("﻿")  # BOM so Excel opens UTF-8 correctly
    w = csv.writer(resp)
    w.writerow(cols)
    for lead in queryset:
        w.writerow([getattr(lead, c) for c in cols])
    return resp


@admin.action(description="Mark selected as Contacted")
def mark_contacted(modeladmin, request, queryset):
    queryset.update(status=Lead.Status.CONTACTED)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("ref", "created_at", "title", "vehicle", "branch", "preferred_date", "name", "phone", "status")
    list_editable = ("status",)
    list_filter = ("status", "lead_type", "branch", "brand", "channel", "created_at")
    search_fields = ("ref", "name", "phone", "reg_no", "model_name", "topic")
    date_hierarchy = "created_at"
    actions = [export_csv, mark_contacted]
    readonly_fields = ("ref", "lead_type", "title", "interest", "brand", "model_name", "vehicle_type", "service_type",
                       "reg_no", "topic", "preferred_date", "branch", "name", "phone", "whatsapp", "channel", "created_at")
    fieldsets = (
        ("Follow-up", {"fields": ("status", "notes")}),
        ("Customer", {"fields": ("name", "phone", "whatsapp", "branch", "preferred_date")}),
        ("Request", {"fields": ("ref", "title", "lead_type", "interest", "brand", "model_name", "vehicle_type",
                                "service_type", "reg_no", "topic")}),
        ("Meta", {"fields": ("channel", "created_at")}),
    )

    @admin.display(description="Vehicle")
    def vehicle(self, obj):
        return obj.model_name or obj.brand or obj.vehicle_type or "–"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user_id", "channel", "direction", "short_text")
    list_filter = ("channel", "direction")
    search_fields = ("user_id", "text")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Text")
    def short_text(self, obj):
        return obj.text[:80]


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("user_id", "channel", "state", "updated_at")
    list_filter = ("channel",)
    search_fields = ("user_id",)

    @admin.display(description="State")
    def state(self, obj):
        return obj.data.get("state", "-")
