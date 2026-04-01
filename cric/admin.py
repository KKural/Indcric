from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Session, Match, Team, Attendance, Payment, SessionPlayer, Poll, Vote


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['first_name', 'last_name', 'username']
    list_display = ['get_display_name', 'username',
                    'email', 'role', 'is_active', 'is_staff']
    search_fields = ['first_name', 'last_name', 'username', 'email']

    @admin.display(description='Name', ordering='first_name')
    def get_display_name(self, obj):
        full = obj.get_full_name()
        return full.title() if full else obj.username.title()


admin.site.register(Session)
admin.site.register(Match)
admin.site.register(Team)
admin.site.register(Attendance)
admin.site.register(Payment)
admin.site.register(SessionPlayer)
admin.site.register(Poll)
admin.site.register(Vote)
