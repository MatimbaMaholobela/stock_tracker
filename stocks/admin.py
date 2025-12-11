from django.contrib import admin
from .models import Organisation, StockPrice, TradingSignal, Report

@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ('ticker', 'name', 'created_at')
    search_fields = ('ticker', 'name')
    list_filter = ('created_at',)

@admin.register(StockPrice)
class StockPriceAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'date', 'close_price')
    list_filter = ('organisation', 'date')
    search_fields = ('organisation__ticker', 'organisation__name')
    date_hierarchy = 'date'

@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ('organisation', 'date', 'signal', 'price_drop', 'expected_profit')
    list_filter = ('signal', 'date', 'organisation')
    search_fields = ('organisation__ticker',)

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'generated_date', 'start_date', 'end_date', 'success_rate')
    list_filter = ('generated_date',)
    readonly_fields = ('generated_date', 'summary')