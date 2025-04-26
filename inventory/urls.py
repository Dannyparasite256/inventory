from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category-list'),
    path('categories/add/', views.CategoryCreateView.as_view(), name='category-add'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category-edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category-delete'),

    # Supplier URLs
    path('suppliers/', views.SupplierListView.as_view(), name='supplier-list'),
    path('suppliers/add/', views.SupplierCreateView.as_view(), name='supplier-add'),
    path('suppliers/<int:pk>/edit/', views.SupplierUpdateView.as_view(), name='supplier-edit'),
    path('suppliers/<int:pk>/delete/', views.SupplierDeleteView.as_view(), name='supplier-delete'),

    # Product URLs
    path('products/', views.ProductListView.as_view(), name='product-list'),
    path('products/add/', views.ProductCreateView.as_view(), name='product-add'),
    path('products/<int:pk>/', views.ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product-edit'),
    path('products/<int:pk>/delete/', views.ProductDeleteView.as_view(), name='product-delete'),

    # Transaction URL
    path('transactions/', views.TransactionListView.as_view(), name='transaction-list'),

    # Receipt URLs
    path('receipts/', views.ReceiptListView.as_view(), name='receipt-list'),
    path('receipts/add/', views.ReceiptCreateView.as_view(), name='receipt-add'),
    path('receipts/<int:pk>/', views.ReceiptDetailView.as_view(), name='receipt-detail'),
    path('receipts/<int:pk>/edit/', views.ReceiptUpdateView.as_view(), name='receipt-edit'),
    path('receipts/<int:pk>/delete/', views.ReceiptDeleteView.as_view(), name='receipt-delete'),

    # Invoice URLs
    path('invoices/', views.InvoiceListView.as_view(), name='invoice-list'),
    path('invoices/add/', views.InvoiceCreateView.as_view(), name='invoice-add'),
    path('invoices/<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice-detail'),
    path('invoices/<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice-edit'),
    path('invoices/<int:pk>/delete/', views.InvoiceDeleteView.as_view(), name='invoice-delete'),
    path('receipts/<int:pk>/pdf/', views.receipt_pdf_view, name='receipt-pdf'),
    path('invoices/<int:pk>/pdf/', views.invoice_pdf_view, name='invoice-pdf'),
    path('invoices/today/', views.TodaysSalesListView.as_view(), name='todays-sales-list'), 
    
    # Report URLs
    path('reports/', views.ReportListView.as_view(), name='report-list'),
    path('reports/view/', views.report_view, name='report-view'),

    path('reports/', views.ReportListView.as_view(), name='report-list'), # Date Range Selection
    path('reports/view/', views.report_view, name='report-view'), # Date Range View (HTML)

    # Daily Sales Report URLs
    path('reports/daily-sales/', views.DailySalesReportSelectView.as_view(), name='daily-sales-report-select'), # New: Date Selection
    path('reports/daily-sales/<str:date_str>/pdf/', views.daily_sales_report_pdf_view, name='daily-sales-report-pdf'), # New: PDF Generation

    path('reports/', views.ReportListView.as_view(), name='report-list'), # Date Range Selection
    path('reports/view/', views.report_view, name='report-view'), # Date Range View (HTML)
    path('reports/profit/', views.ProfitReportView.as_view(), name='profit-report'), # NEW: Profit Report
    path('reports/daily-sales/', views.DailySalesReportSelectView.as_view(), name='daily-sales-report-select'),
    path('reports/daily-sales/<str:date_str>/pdf/', views.daily_sales_report_pdf_view, name='daily-sales-report-pdf'),
    path('activity/today/', views.DailyActivityView.as_view(), name='daily-activity'),

]