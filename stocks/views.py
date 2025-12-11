from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import json
from datetime import datetime, timedelta
from .models import Organisation, StockPrice, TradingSignal, Report
from .forms import StockDataUploadForm
from .utils import process_uploaded_file, StockAnalyzer, get_recent_data
from django.utils import timezone
from datetime import datetime

from datetime import datetime, timedelta

def dashboard(request):
    """Main dashboard view"""
    organisations = Organisation.objects.all().order_by('-created_at')
    recent_signals = TradingSignal.objects.select_related('organisation').order_by('-date')[:10]
    
    # Calculate buy signals count
    buy_signals_count = TradingSignal.objects.filter(signal='buy').count()
    
    context = {
        'organizations': organisations,  
        'recent_signals': recent_signals,
        'total_organizations': organisations.count(),
        'total_prices': StockPrice.objects.count(),
        'buy_signals_count': buy_signals_count,
    }
    return render(request, 'stocks/dashboard.html', context)

def upload_data(request):
    """Handle file uploads"""
    if request.method == 'POST':
        form = StockDataUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file = request.FILES['file']
                
                if file.name.endswith('.csv'):
                    # Use process_uploaded_file instead of process_csv_file
                    orgs_created, prices_created = process_uploaded_file(file, form.cleaned_data)
                    messages.success(
                        request,
                        f'Successfully uploaded data! Created {orgs_created} organisations '
                        f'and {prices_created} price records.'
                    )
                    return redirect('stocks:dashboard')
                else:
                    messages.error(request, 'Currently only CSV files are supported.')
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
    else:
        form = StockDataUploadForm()
    
    return render(request, 'stocks/upload.html', {'form': form})

def stock_detail(request, ticker):
    """View detailed stock analysis"""
    organisation = get_object_or_404(Organisation, ticker=ticker)
    
    # Get data for analysis
    prices = StockPrice.objects.filter(organisation=organisation).order_by('date')
    
    if prices.count() < 6:
        messages.warning(request, 'Insufficient data for analysis (need at least 6 days)')
        return redirect('stocks:dashboard')
    
    # Prepare data for analyzer
    prices_data = []
    for price in prices:
        prices_data.append({
            'date': price.date,
            'close_price': price.close_price
        })
    
    analyzer = StockAnalyzer(ticker, prices_data)
    signals = analyzer.generate_signals()
    summary = analyzer.get_summary_stats(signals)
    
    # Get recent data (last 30 days)
    recent_data = get_recent_data(organisation, days=30)
    
    # Get recent prices for display
    recent_prices = prices.order_by('-date')[:50]
    
    context = {
        'organisation': organisation,
        'signals': signals[-30:],  # Last 30 days
        'summary': summary,
        'recent_data': json.dumps(recent_data),
        'prices': recent_prices,
        'total_prices': prices.count(),
    }
    
    return render(request, 'stocks/stock_detail.html', context)

def generate_report(request):
    """Generate analysis report"""
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if not start_date or not end_date:
            messages.error(request, 'Please provide both start and end dates')
            return redirect('stocks:reports')
        
        # Get all organisations
        organisations = Organisation.objects.all()
        report_data = []
        total_buys = 0
        total_successful = 0
        
        for org in organisations:
            # Get signals in date range
            signals = TradingSignal.objects.filter(
                organisation=org,
                date__gte=start_date,
                date__lte=end_date
            )
            
            buy_signals = signals.filter(signal='buy')
            sell_signals = signals.filter(signal='sell')
            successful_buys = buy_signals.filter(expected_profit__gt=0)
            
            success_rate = (successful_buys.count() / buy_signals.count() * 100) if buy_signals.count() > 0 else 0
            
            org_data = {
                'ticker': org.ticker,
                'total_signals': signals.count(),
                'buy_signals': buy_signals.count(),
                'sell_signals': sell_signals.count(),
                'successful_buys': successful_buys.count(),
                'success_rate': round(success_rate, 2),
            }
            
            report_data.append(org_data)
            total_buys += buy_signals.count()
            total_successful += successful_buys.count()
        
        # Calculate overall success rate
        overall_success_rate = (total_successful / total_buys * 100) if total_buys > 0 else 0
        
        # Create report
        report = Report.objects.create(
            title=f"Stock Analysis Report {start_date} to {end_date}",
            start_date=start_date,
            end_date=end_date,
            summary=report_data,
            total_signals=sum(item['total_signals'] for item in report_data),
            successful_buys=total_successful,
            success_rate=round(overall_success_rate, 2),
        )
        
        messages.success(request, f'Report generated successfully!')
        
        return redirect('stocks:report_detail', report_id=report.id)
    
    # Default: show last 30 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    reports = Report.objects.all().order_by('-generated_date')
    
    return render(request, 'stocks/reports.html', {
        'reports': reports,
        'default_start': start_date.strftime('%Y-%m-%d'),
        'default_end': end_date.strftime('%Y-%m-%d'),
    })


def report_detail(request, report_id):
    """View detailed report"""
    report = get_object_or_404(Report, id=report_id)
    report_data = report.summary
    
    # Calculate totals from report data
    total_buys = sum(item['buy_signals'] for item in report_data)
    total_successful = report.successful_buys
    
    context = {
        'report': report,
        'report_data': report_data,
        'total_buys': total_buys,
        'total_successful': total_successful,
        'overall_success_rate': report.success_rate,
    }
    
    return render(request, 'stocks/report_detail.html', context)

def api_get_stock_data(request, ticker):
    """API endpoint for stock data (for charts)"""
    organisation = get_object_or_404(Organisation, ticker=ticker)
    days = int(request.GET.get('days', 30))
    
    data = get_recent_data(organisation, days)
    return JsonResponse(data)


def delete_organisation(request, ticker):
    """Delete organisation and all related data"""
    organisation = get_object_or_404(Organisation, ticker=ticker)  
    
    if request.method == 'POST':
        org_name = organisation.ticker
        organisation.delete()
        messages.success(request, f'Successfully deleted {org_name}')
        return redirect('stocks:dashboard')  
    
    return render(request, 'stocks/confirm_delete.html', {'organisation': organisation})