from django.contrib import admin
from .models import Match, Team, Player, Innings, Delivery, PlayerSessionStat

admin.site.register(Match)
admin.site.register(Team)
admin.site.register(Player)


@admin.register(PlayerSessionStat)
class PlayerSessionStatAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'session', 'runs', 'balls_faced', 'wickets',
        'balls_bowled', 'catches', 'stumpings', 'computed_at',
    )
    list_filter = ('session',)
    search_fields = ('user__username', 'session__name')
    ordering = ('-session__date', 'user__username')


@admin.register(Innings)
class InningsAdmin(admin.ModelAdmin):
    list_display = ('match', 'number', 'batting_team',
                    'bowling_team', 'is_closed')
    list_filter = ('is_closed',)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'innings', 'sequence', 'over_number', 'ball_in_over',
        'striker', 'bowler', 'runs_off_bat', 'extra_type', 'extra_runs', 'is_wicket',
    )
    list_filter = ('extra_type', 'is_wicket')
    ordering = ('innings', 'sequence')
