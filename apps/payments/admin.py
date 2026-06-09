from django.contrib import admin
from .models import Payment, Wallet, DrinkRound

admin.site.register(Payment)
admin.site.register(Wallet)


@admin.register(DrinkRound)
class DrinkRoundAdmin(admin.ModelAdmin):
    list_display = ('session', 'drink_type', 'payer',
                    'recorded_by', 'recorded_at')
    list_filter = ('drink_type', 'session')
    search_fields = ('payer__username', 'session__name')
    ordering = ('-recorded_at',)
