from django.db import models
from django.core.validators import MinValueValidator

class Organisation(models.Model):
    ticker = models.CharField(
        max_length=20, 
        unique=True,
        help_text="Stock exchange ticker symbol (e.g., OMN-ZA, AFE-ZA)")
    
    name = models.CharField(
        max_length=200, 
        blank=True,
        help_text="Full company name")
    
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.ticker} - {self.name}" if self.name else self.ticker

class StockPrice(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='prices')
    date = models.DateField()
    close_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    volume = models.BigIntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['organisation', 'date']
    
    def __str__(self):
        return f"{self.organisation.ticker} - {self.date}: {self.close_price}"

class TradingSignal(models.Model):
    BUY = 'buy'
    SELL = 'sell'
    HOLD = 'hold'
    SIGNAL_CHOICES = [
        (BUY, 'Buy'),
        (SELL, 'Sell'),
        (HOLD, 'Hold'),
    ]
    
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='signals')
    date = models.DateField()
    signal = models.CharField(max_length=4, choices=SIGNAL_CHOICES)
    price_drop = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # percentage drop
    expected_profit = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # expected profit percentage
    analysis_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['organisation', 'date']
    
    def __str__(self):
        return f"{self.organisation.ticker} - {self.date}: {self.signal}"

class Report(models.Model):
    title = models.CharField(max_length=200)
    generated_date = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField()
    summary = models.JSONField()  # Stores analysis results
    total_signals = models.IntegerField(default=0)
    successful_buys = models.IntegerField(default=0)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    def __str__(self):
        return f"Report {self.id}: {self.title}"