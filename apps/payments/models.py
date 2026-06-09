from django.db import models


class Payment(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    session = models.ForeignKey(
        'cric_sessions.Session', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='pending')
    date = models.DateField(auto_now_add=True)
    method = models.CharField(
        max_length=20, default='wallet')  # 'wallet' or 'cash'

    class Meta:
        unique_together = ('user', 'session')


class Wallet(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='pending')
    date = models.DateField(auto_now_add=True)


class DrinkRound(models.Model):
    """Records who paid for drinks (alcohol or non-alcohol) at a session.

    One row per drink type per session — enforced by unique_together.
    The next-payer algorithm reads these rows to find who paid longest ago.
    """

    ALCOHOL = 'alcohol'
    NON_ALCOHOL = 'non_alcohol'
    DRINK_TYPE_CHOICES = [
        (ALCOHOL, 'Alcohol'),
        (NON_ALCOHOL, 'Non-alcoholic / Soft drinks'),
    ]

    session = models.ForeignKey(
        'cric_sessions.Session',
        on_delete=models.CASCADE,
        related_name='drink_rounds',
    )
    payer = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='drink_rounds_paid',
    )
    drink_type = models.CharField(max_length=15, choices=DRINK_TYPE_CHOICES)
    recorded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='drink_rounds_recorded',
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('session', 'drink_type')]

    def __str__(self):
        return f"{self.get_drink_type_display()} @ {self.session.name} — paid by {self.payer.username}"
