from django.urls import path
from . import views

app_name = 'stocks'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('upload/', views.upload_data, name='upload'),
    path('stock/<str:ticker>/', views.stock_detail, name='stock_detail'),
    path('reports/', views.generate_report, name='reports'),
    path('reports/<int:report_id>/', views.report_detail, name='report_detail'),
    path('delete/<str:ticker>/', views.delete_organisation, name='delete_organisation'),
    path('api/stock/<str:ticker>/', views.api_get_stock_data, name='api_stock_data'),
]