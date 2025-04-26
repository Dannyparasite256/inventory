# inventory/views.py

# --- Django Imports ---
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Sum, F, Q, Count
from django.utils import timezone
from django.http import HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.template.loader import render_to_string
from django.contrib import messages
from django import forms # Needed for InvoiceFilterForm ValidationError

# --- Third-Party Imports ---
from dateutil.parser import parse # For parsing dates in date range report
from datetime import datetime # For parsing date in daily sales report PDF view

# --- WeasyPrint Import (with error handling) ---
try:
    from weasyprint import HTML, CSS
except ImportError:
    HTML = None # Set HTML to None if WeasyPrint is not installed
    CSS = None
    # Optional: Add logging for server startup if needed
    # import logging
    # logging.warning("WeasyPrint library not found. PDF generation disabled.")

# --- Local Imports ---
from .models import (
    Product, Category, Supplier, Transaction, Receipt, Invoice,
    ReceiptItem, InvoiceItem
)
from .forms import (
    ProductForm, CategoryForm, SupplierForm, ProductFilterForm,
    ReceiptForm, ReceiptItemFormSet, InvoiceForm, InvoiceItemFormSet,
    DateRangeReportForm, DailySalesReportForm # Make sure DailySalesReportForm is imported
)

# --- Permissions Mixin ---
class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to ensure user is logged in and is staff."""
    login_url = 'login' # Redirect non-logged-in users to login

    def test_func(self):
        # Check if user is authenticated AND is staff
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        # Handle cases where user is logged in but not staff
        if self.request.user.is_authenticated:
            messages.error(self.request, "You do not have permission to access this page.")
            return redirect('dashboard') # Redirect authenticated non-staff to dashboard
        # Handle non-authenticated users (should be caught by LoginRequiredMixin, but good fallback)
        return super().handle_no_permission()

# --- Dashboard View ---
@login_required
def dashboard(request):
    total_products = Product.objects.count()
    # Count products where quantity is less than or equal to reorder level
    low_stock_products = Product.objects.filter(quantity__lte=F('reorder_level')).count()
    total_suppliers = Supplier.objects.count()
    total_categories = Category.objects.count()
    # Get the 10 most recent transactions
    recent_transactions = Transaction.objects.select_related('product', 'user').order_by('-timestamp')[:10]

    # Calculate basic sales for today (optional for dashboard)
    today = timezone.now().date()
    todays_sales_summary = Invoice.objects.filter(sale_date=today).aggregate(
        total_sales=Sum('total_amount'),
        invoice_count=Count('id')
    )

    context = {
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'total_suppliers': total_suppliers,
        'total_categories': total_categories,
        'recent_transactions': recent_transactions,
        'todays_total_sales': todays_sales_summary.get('total_sales') or 0.00,
        'todays_invoice_count': todays_sales_summary.get('invoice_count') or 0,
        'page_title': 'Dashboard'
    }
    return render(request, 'inventory/dashboard.html', context)

# --- Category Views (CRUD) ---
class CategoryListView(StaffRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories' # Explicitly set context name
    paginate_by = 15
    ordering = ['name'] # Order alphabetically

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Product Categories'
        return context

class CategoryCreateView(StaffRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('category-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Add New Category'
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class CategoryUpdateView(StaffRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    success_url = reverse_lazy('category-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Update Category: {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

class CategoryDeleteView(StaffRequiredMixin, DeleteView):
    model = Category
    # Use a generic confirmation template or create specific one
    template_name = 'inventory/confirm_delete_base.html'
    success_url = reverse_lazy('category-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Delete Category: {self.object.name}'
        context['object_type'] = 'Category' # Pass type to template
        context['cancel_url'] = reverse_lazy('category-list') # URL for cancel button
        return context

    def post(self, request, *args, **kwargs):
        category = self.get_object()
        # Prevent deletion if category is linked to products
        if category.products.exists():
            messages.error(request, f"Cannot delete category '{category.name}' as it is linked to existing products.")
            return redirect('category-list')
        messages.success(request, f"Category '{category.name}' deleted successfully.")
        return super().post(request, *args, **kwargs)

# --- Supplier Views (CRUD) ---
class SupplierListView(StaffRequiredMixin, ListView):
    model = Supplier
    template_name = 'inventory/supplier_list.html'
    context_object_name = 'suppliers' # Explicit context name
    paginate_by = 15
    ordering = ['name']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Suppliers'
        return context

class SupplierCreateView(StaffRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('supplier-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Add New Supplier'
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{form.instance.name}' created successfully.")
        return super().form_valid(form)

class SupplierUpdateView(StaffRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'inventory/supplier_form.html'
    success_url = reverse_lazy('supplier-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Update Supplier: {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{form.instance.name}' updated successfully.")
        return super().form_valid(form)

class SupplierDeleteView(StaffRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'inventory/confirm_delete_base.html' # Reusable delete template
    success_url = reverse_lazy('supplier-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Delete Supplier: {self.object.name}'
        context['object_type'] = 'Supplier'
        context['cancel_url'] = reverse_lazy('supplier-list')
        return context

    def post(self, request, *args, **kwargs):
        supplier = self.get_object()
        # Prevent deletion if linked to products or receipts
        if supplier.products.exists() or supplier.receipts.exists():
             messages.error(request, f"Cannot delete supplier '{supplier.name}' as it's linked to products or receipts.")
             return redirect('supplier-list')
        messages.success(request, f"Supplier '{supplier.name}' deleted successfully.")
        return super().post(request, *args, **kwargs)

# --- Product Views (CRUD + Search/Filter) ---
class ProductListView(LoginRequiredMixin, ListView): # All logged-in users can view
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 10
    ordering = ['name'] # Default ordering

    def get_queryset(self):
        # Optimize by fetching related category and supplier in the initial query
        queryset = super().get_queryset().select_related('category', 'supplier')
        form = ProductFilterForm(self.request.GET)

        # Apply filters if the form is valid
        if form.is_valid():
            name = form.cleaned_data.get('name')
            category = form.cleaned_data.get('category')
            supplier = form.cleaned_data.get('supplier')
            below_reorder = form.cleaned_data.get('below_reorder')

            if name:
                # Filter by name OR sku containing the search term (case-insensitive)
                queryset = queryset.filter(Q(name__icontains=name) | Q(sku__icontains=name))
            if category:
                queryset = queryset.filter(category=category)
            if supplier:
                queryset = queryset.filter(supplier=supplier)
            if below_reorder:
                # Filter where quantity is less than or equal to the reorder_level field
                queryset = queryset.filter(quantity__lte=F('reorder_level'))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass the filter form instance (bound with GET data or unbound) to the template
        context['filter_form'] = ProductFilterForm(self.request.GET or None)
        context['page_title'] = 'Products'
        return context

class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'

    def get_queryset(self):
        # Optimize detail view query as well
        return super().get_queryset().select_related('category', 'supplier')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get recent transactions for this specific product
        context['transactions'] = Transaction.objects.filter(
            product=self.object
        ).select_related('user').order_by('-timestamp')[:10]
        context['page_title'] = f'Product: {self.object.name}'
        return context

class ProductCreateView(StaffRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Add New Product'
        return context

    def form_valid(self, form):
        # Initial stock should be added via Receipts/Adjustments, not here.
        product = form.save() # Save directly if quantity isn't handled here
        messages.success(self.request, f"Product '{product.name}' created successfully.")
        # Redirect to the detail view of the newly created product
        return HttpResponseRedirect(product.get_absolute_url())

class ProductUpdateView(StaffRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Update Product: {self.object.name}'
        return context

    def form_valid(self, form):
        product = form.save()
        messages.success(self.request, f"Product '{product.name}' updated successfully.")
        # Redirect to detail view after update
        return HttpResponseRedirect(product.get_absolute_url())

class ProductDeleteView(StaffRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/confirm_delete_base.html' # Reusable template
    success_url = reverse_lazy('product-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Delete Product: {self.object.name}'
        context['object_type'] = 'Product'
        # Define cancel URL to go back to product detail
        context['cancel_url'] = self.object.get_absolute_url() if self.object else reverse_lazy('product-list')
        # Add extra warning about potential data loss (optional)
        context['warning_message'] = "Deleting this product cannot be undone. Consider implications if it exists on past receipts or invoices."
        return context

    def post(self, request, *args, **kwargs):
        # Consider adding checks here if strict prevention of deletion is needed,
        # e.g., if product has associated transactions.
        product = self.get_object()
        messages.success(request, f"Product '{product.name}' deleted successfully.")
        return super().post(request, *args, **kwargs)

# --- Transaction View ---
class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'inventory/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 25 # Show more transactions per page
    ordering = ['-timestamp']

    def get_queryset(self):
        # Optimize by fetching related product and user
        queryset = super().get_queryset().select_related('product', 'user')
        # Basic filtering example (can be expanded with a dedicated form)
        product_id = self.request.GET.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Inventory Transactions Log'
        return context

# --- Receipt Views (CRUD with Formsets) ---
class ReceiptListView(LoginRequiredMixin, ListView):
    model = Receipt
    template_name = 'inventory/receipt_list.html'
    context_object_name = 'receipts'
    paginate_by = 15
    ordering = ['-purchase_date', '-created_at']

    def get_queryset(self):
        # Optimize query
        return super().get_queryset().select_related('supplier', 'created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Purchase Receipts'
        return context

class ReceiptDetailView(LoginRequiredMixin, DetailView):
    model = Receipt
    template_name = 'inventory/receipt_detail.html'
    context_object_name = 'receipt'

    def get_queryset(self):
        # Prefetch related items and their products for efficiency
        return super().get_queryset().prefetch_related(
            'items__product' # Prefetch items and the product linked to each item
        ).select_related('supplier', 'created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Receipt Details: {self.object.receipt_number}'
        return context

class ReceiptCreateView(StaffRequiredMixin, CreateView):
    model = Receipt
    form_class = ReceiptForm
    template_name = 'inventory/receipt_form.html' # Uses specific template extending _form_base.html

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        # Initialize formset based on request type (POST or GET)
        if self.request.POST:
            data['items_formset'] = ReceiptItemFormSet(self.request.POST, prefix='items')
        else:
            data['items_formset'] = ReceiptItemFormSet(prefix='items')
        data['page_title'] = 'Create New Receipt'
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']

        # Use atomic transaction for data integrity
        with db_transaction.atomic():
            form.instance.created_by = self.request.user # Assign current user
            self.object = form.save() # Save the main Receipt object

            # Check if the formset is valid
            if items_formset.is_valid():
                items_formset.instance = self.object # Link formset items to the saved Receipt
                items_formset.save() # Save ReceiptItem objects (triggers stock updates via model save)
                # Receipt total calculation also happens in ReceiptItem save() or can be triggered here
                # self.object.calculate_total() # Ensure total is calculated after all items are saved
                messages.success(self.request, f"Receipt '{self.object.receipt_number}' created successfully.")
                return HttpResponseRedirect(self.get_success_url()) # Redirect on success
            else:
                # Formset is invalid, transaction automatically rolled back by context manager exit
                messages.error(self.request, "Please correct the errors in the receipt items below.")
                # Re-render the form with errors (main form + formset errors)
                return self.form_invalid(form)

    def form_invalid(self, form):
        """Handles cases where the main form or formset is invalid."""
        # Ensure formset with errors is passed back to the template
        context = self.get_context_data() # Re-get context to ensure formset is evaluated
        items_formset = context['items_formset']
        # Pass the invalid main form and the (potentially invalid) formset back
        return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

    def get_success_url(self):
        # Redirect to the detail view of the newly created receipt
        return reverse('receipt-detail', kwargs={'pk': self.object.pk})

class ReceiptUpdateView(StaffRequiredMixin, UpdateView):
    model = Receipt
    form_class = ReceiptForm
    template_name = 'inventory/receipt_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        # Initialize formset with existing instance
        if self.request.POST:
            data['items_formset'] = ReceiptItemFormSet(self.request.POST, instance=self.object, prefix='items')
        else:
            data['items_formset'] = ReceiptItemFormSet(instance=self.object, prefix='items')
        data['page_title'] = f'Update Receipt: {self.object.receipt_number}'
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']

        with db_transaction.atomic():
            self.object = form.save() # Save changes to main Receipt

            if items_formset.is_valid():
                items_formset.instance = self.object
                # Handle stock reversal for deleted/changed items - requires custom logic or signals
                # For now, saving the formset handles additions/updates based on its logic
                items_formset.save()
                # Ensure total is recalculated after all changes
                self.object.calculate_total()
                messages.success(self.request, f"Receipt '{self.object.receipt_number}' updated successfully.")
                return HttpResponseRedirect(self.get_success_url())
            else:
                messages.error(self.request, "Please correct the errors in the receipt items below.")
                return self.form_invalid(form)

    def form_invalid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

    def get_success_url(self):
        # Redirect to detail view after update
        return reverse('receipt-detail', kwargs={'pk': self.object.pk})

class ReceiptDeleteView(StaffRequiredMixin, DeleteView):
    model = Receipt
    template_name = 'inventory/confirm_delete_base.html' # Reusable template
    success_url = reverse_lazy('receipt-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Delete Receipt: {self.object.receipt_number}'
        context['object_type'] = 'Receipt'
        context['cancel_url'] = self.object.get_absolute_url() if self.object else reverse_lazy('receipt-list')
        # Add a specific warning for receipt deletion
        context['warning_message'] = "Deleting this receipt will attempt to reverse the stock quantities added by its items. This might affect current stock levels."
        return context

    def post(self, request, *args, **kwargs):
        receipt = self.get_object()
        with db_transaction.atomic():
            try:
                # Attempt to reverse stock for each item before deleting the receipt
                for item in receipt.items.all():
                     Transaction.objects.create(
                         product=item.product,
                         transaction_type='ADJ', # Or a specific 'RECEIPT_DELETE' type
                         quantity=-item.quantity, # Negative quantity to reverse effect
                         user=request.user,
                         notes=f"Stock reversed due to deletion of Receipt {receipt.receipt_number}"
                     )
                # If stock reversal is successful (or no items), proceed with deletion
                messages.success(request, f"Receipt '{receipt.receipt_number}' deleted. Stock levels adjusted (reversed).")
                return super().post(request, *args, **kwargs)
            except Exception as e:
                 # Handle potential errors during stock reversal (e.g., product deleted)
                 messages.error(request, f"Error reversing stock for Receipt {receipt.receipt_number}: {e}. Deletion aborted.")
                 # Redirect back to detail view if deletion fails
                 return redirect(receipt.get_absolute_url())

# --- Invoice Filter Form ---
# (Defined here for use in InvoiceListView)
class InvoiceFilterForm(forms.Form):
    customer_name = forms.CharField(required=False, label="Customer", widget=forms.TextInput(attrs={'placeholder': 'Search customer...'}))
    invoice_number = forms.CharField(required=False, label="Invoice #", widget=forms.TextInput(attrs={'placeholder': 'Search number...'}))
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class':'form-control'}), required=False)
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class':'form-control'}), required=False)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            # Use forms.ValidationError for form-level errors
            raise forms.ValidationError("End date cannot be earlier than start date.")
        return cleaned_data

# --- Invoice Views (CRUD with Formsets + Filtering + Today's Sales) ---
class InvoiceListView(LoginRequiredMixin, ListView): # View All Invoices
    model = Invoice
    template_name = 'inventory/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 15
    ordering = ['-sale_date', '-created_at']

    def get_queryset(self):
        queryset = super().get_queryset().select_related('created_by')
        form = InvoiceFilterForm(self.request.GET) # Initialize filter form with GET data

        # Apply filters if form is submitted and valid
        if form.is_valid():
            customer_name = form.cleaned_data.get('customer_name')
            invoice_number = form.cleaned_data.get('invoice_number')
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')

            if customer_name:
                queryset = queryset.filter(customer_name__icontains=customer_name)
            if invoice_number:
                queryset = queryset.filter(invoice_number__icontains=invoice_number)
            if start_date:
                queryset = queryset.filter(sale_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(sale_date__lte=end_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass filter form instance to template
        context['filter_form'] = InvoiceFilterForm(self.request.GET or None)
        context['page_title'] = 'All Sales Invoices'
        return context

class TodaysSalesListView(LoginRequiredMixin, ListView): # View for Today's Sales ONLY
    model = Invoice
    template_name = 'inventory/todays_sales.html'
    context_object_name = 'todays_invoices'
    # Typically no pagination needed for a single day

    def get_queryset(self):
        """Filter invoices where sale_date is today."""
        today = timezone.now().date()
        return super().get_queryset().filter(sale_date=today).select_related('created_by').order_by('created_at')

    def get_context_data(self, **kwargs):
        """Add today's date and sales totals to context."""
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        # Calculate totals for today's invoices
        totals = self.get_queryset().aggregate(
            total_sales=Sum('total_amount'),
            invoice_count=Count('id')
        )
        context['today_date'] = today
        context['total_sales_today'] = totals.get('total_sales') or 0.00
        context['invoice_count_today'] = totals.get('invoice_count') or 0
        context['page_title'] = f'Sales for Today ({today.strftime("%Y-%m-%d")})'
        return context

class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'inventory/invoice_detail.html'
    context_object_name = 'invoice'

    def get_queryset(self):
        # Optimize by prefetching items and related product/user
        return super().get_queryset().prefetch_related(
            'items__product'
        ).select_related('created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Invoice Details: {self.object.invoice_number}'
        return context

class InvoiceCreateView(StaffRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'inventory/invoice_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items_formset'] = InvoiceItemFormSet(self.request.POST, prefix='items')
        else:
            data['items_formset'] = InvoiceItemFormSet(prefix='items')
        data['page_title'] = 'Create New Invoice'
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']

        with db_transaction.atomic():
            form.instance.created_by = self.request.user # Assign user
            # Don't save main form yet if formset is invalid
            if items_formset.is_valid():
                # Save main form first to get PK for formset FK
                self.object = form.save()
                items_formset.instance = self.object
                items_formset.save() # Triggers InvoiceItem save, stock deduction, total calculation
                messages.success(self.request, f"Invoice '{self.object.invoice_number}' created successfully.")
                return HttpResponseRedirect(self.get_success_url())
            else:
                # Formset invalid, transaction rolled back
                messages.error(self.request, "Please correct the errors in the invoice items below (check stock levels).")
                # Re-render form with main form data and invalid formset
                return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

    def form_invalid(self, form):
        # Handle main form invalid OR formset invalid (caught in form_valid)
        context = self.get_context_data()
        items_formset = context.get('items_formset') # Get potentially invalid formset
        # Pass both form and formset (with errors) back to template
        return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

    def get_success_url(self):
        return reverse('invoice-detail', kwargs={'pk': self.object.pk})

class InvoiceUpdateView(StaffRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'inventory/invoice_form.html'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items_formset'] = InvoiceItemFormSet(self.request.POST, instance=self.object, prefix='items')
        else:
            data['items_formset'] = InvoiceItemFormSet(instance=self.object, prefix='items')
        data['page_title'] = f'Update Invoice: {self.object.invoice_number}'
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']

        with db_transaction.atomic():
            # Need robust stock handling for updates/deletions here or via signals
            if items_formset.is_valid():
                self.object = form.save() # Save main invoice changes
                items_formset.instance = self.object
                items_formset.save() # Saves changes, additions, deletions
                # Ensure totals are recalculated after formset save
                self.object.calculate_totals()
                messages.success(self.request, f"Invoice '{self.object.invoice_number}' updated successfully.")
                return HttpResponseRedirect(self.get_success_url())
            else:
                messages.error(self.request, "Please correct the errors in the invoice items below (check stock levels).")
                return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

    def form_invalid(self, form):
        context = self.get_context_data()
        items_formset = context.get('items_formset')
        return self.render_to_response(self.get_context_data(form=form, items_formset=items_formset))

    def get_success_url(self):
        return reverse('invoice-detail', kwargs={'pk': self.object.pk})

class InvoiceDeleteView(StaffRequiredMixin, DeleteView):
    model = Invoice
    template_name = 'inventory/confirm_delete_base.html' # Reusable template
    success_url = reverse_lazy('invoice-list') # Go back to list view on success

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'Delete Invoice: {self.object.invoice_number}'
        context['object_type'] = 'Invoice'
        context['cancel_url'] = self.object.get_absolute_url() if self.object else reverse_lazy('invoice-list')
        context['warning_message'] = "Deleting this invoice will attempt to return the stock quantities deducted by its items. This might affect current stock levels."
        return context

    def post(self, request, *args, **kwargs):
        invoice = self.get_object()
        with db_transaction.atomic():
            try:
                # Attempt stock return before deleting
                for item in invoice.items.all():
                     Transaction.objects.create(
                         product=item.product,
                         transaction_type='IN', # Stock comes back IN
                         quantity=item.quantity,
                         user=request.user,
                         notes=f"Stock returned due to deletion of Invoice {invoice.invoice_number}"
                     )
                messages.success(request, f"Invoice '{invoice.invoice_number}' deleted. Stock levels adjusted (returned).")
                # Proceed with actual deletion via superclass method
                return super().post(request, *args, **kwargs)
            except Exception as e:
                 messages.error(request, f"Error returning stock for Invoice {invoice.invoice_number}: {e}. Deletion aborted.")
                 return redirect(invoice.get_absolute_url())

# --- Date Range Report Views ---
class ReportListView(StaffRequiredMixin, FormView):
    """View to display the date range selection form for the comprehensive report."""
    template_name = 'inventory/report_list.html'
    form_class = DateRangeReportForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Generate Date Range Report'
        return context

    def form_valid(self, form):
        """Store selected dates in session and redirect to the report display view."""
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        self.request.session['report_start_date'] = start_date.isoformat()
        self.request.session['report_end_date'] = end_date.isoformat()
        return redirect('report-view')

@login_required
def report_view(request):
    """Displays the comprehensive report based on dates stored in the session."""
    start_date_str = request.session.get('report_start_date')
    end_date_str = request.session.get('report_end_date')

    if not start_date_str or not end_date_str:
        messages.error(request, "Please select a date range first.")
        return redirect('report-list')

    try:
        start_date = parse(start_date_str).date()
        # Include the entire end date day by setting time to end of day
        end_date_dt = parse(end_date_str).replace(hour=23, minute=59, second=59, microsecond=999999)
        end_date = end_date_dt.date() # Use date part for filtering date fields
    except ValueError:
        messages.error(request, "Invalid date format stored.")
        return redirect('report-list')

    # --- Gather Report Data ---
    transactions = Transaction.objects.filter(
        timestamp__date__gte=start_date, timestamp__date__lte=end_date
    ).select_related('product', 'user').order_by('timestamp')

    sales_summary = Invoice.objects.filter(
        sale_date__gte=start_date, sale_date__lte=end_date
    ).aggregate(
        total_sales=Sum('total_amount'), total_sub_total=Sum('sub_total'),
        total_tax=Sum('tax_amount'), total_discount=Sum('discount_amount'),
        invoice_count=Count('id')
    )

    purchase_summary = Receipt.objects.filter(
        purchase_date__gte=start_date, purchase_date__lte=end_date
    ).aggregate(
        total_purchases=Sum('total_amount'), receipt_count=Count('id')
    )

    top_selling_products = InvoiceItem.objects.filter(
        invoice__sale_date__gte=start_date, invoice__sale_date__lte=end_date
    ).values('product__name').annotate(
        total_quantity_sold=Sum('quantity'),
        total_revenue=Sum(F('quantity') * F('unit_price'))
    ).order_by('-total_quantity_sold')[:10]

    low_stock_products = Product.objects.filter(quantity__lte=F('reorder_level')).order_by('quantity')

    context = {
        'start_date': start_date,
        'end_date': end_date,
        'transactions': transactions,
        'sales_summary': sales_summary,
        'purchase_summary': purchase_summary,
        'top_selling_products': top_selling_products,
        'low_stock_products': low_stock_products,
        'page_title': f'Report: {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}'
    }

    return render(request, 'inventory/report_view.html', context)

# --- Daily Sales Report Views ---
class DailySalesReportSelectView(LoginRequiredMixin, FormView):
    """View to select the date for the daily sales report PDF."""
    template_name = 'inventory/daily_sales_report_select.html'
    form_class = DailySalesReportForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Select Daily Sales Report Date'
        return context

    def form_valid(self, form):
        """Redirect to the PDF generation view with the selected date."""
        report_date = form.cleaned_data['report_date']
        date_str = report_date.isoformat() # Format as YYYY-MM-DD
        pdf_url = reverse('daily-sales-report-pdf', kwargs={'date_str': date_str})
        return HttpResponseRedirect(pdf_url)

# --- PDF Generation Views ---
@login_required
def receipt_pdf_view(request, pk):
    """Generates and serves a PDF for a specific receipt."""
    if HTML is None:
        messages.error(request, "PDF generation library (WeasyPrint) is not installed.")
        return redirect('receipt-detail', pk=pk) # Redirect back to detail view

    receipt = get_object_or_404(Receipt.objects.prefetch_related('items__product'), pk=pk)
    context = {'receipt': receipt, 'request': request}
    html_string = render_to_string('inventory/receipt_pdf.html', context)

    try:
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="receipt_{receipt.receipt_number}.pdf"' # Show inline or attachment
        return response
    except Exception as e:
        # Catch potential WeasyPrint errors (e.g., missing system deps)
        messages.error(request, f"Error generating PDF: {e}")
        return redirect('receipt-detail', pk=pk)

@login_required
def invoice_pdf_view(request, pk):
    """Generates and serves a PDF for a specific invoice."""
    if HTML is None:
        messages.error(request, "PDF generation library (WeasyPrint) is not installed.")
        return redirect('invoice-detail', pk=pk)

    invoice = get_object_or_404(Invoice.objects.prefetch_related('items__product'), pk=pk)
    context = {'invoice': invoice, 'request': request}
    html_string = render_to_string('inventory/invoice_pdf.html', context)

    try:
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice_{invoice.invoice_number}.pdf"' # Show inline or attachment
        return response
    except Exception as e:
        messages.error(request, f"Error generating PDF: {e}")
        return redirect('invoice-detail', pk=pk)

@login_required
def daily_sales_report_pdf_view(request, date_str):
    """Generates and serves a PDF summarizing sales for a specific date."""
    if HTML is None:
        messages.error(request, "PDF generation library (WeasyPrint) is not installed.")
        return redirect('daily-sales-report-select')

    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, "Invalid date format.")
        return redirect('daily-sales-report-select')

    invoices_for_day = Invoice.objects.filter(sale_date=report_date).order_by('invoice_number')
    sales_summary = invoices_for_day.aggregate(
        total_sales=Sum('total_amount'), invoice_count=Count('id')
    )

    context = {
        'report_date': report_date,
        'invoices': invoices_for_day,
        'total_sales': sales_summary.get('total_sales') or 0.00,
        'invoice_count': sales_summary.get('invoice_count') or 0,
        'request': request,
    }

    html_string = render_to_string('inventory/daily_sales_report_pdf.html', context)

    try:
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="daily_sales_{date_str}.pdf"' # Show inline or attachment
        return response
    except Exception as e:
        messages.error(request, f"Error generating PDF: {e}")
        return redirect('daily-sales-report-select')
    


# inventory/views.py

# ... (keep existing imports)
from django.views.generic import TemplateView # Import TemplateView

# ... (keep WeasyPrint imports and check)
# ... (keep other forms and models imports)

# ... (keep existing views: StaffRequiredMixin, dashboard, CRUD views, Reports, PDFs...)


# --- NEW: Daily Activity View ---

class DailyActivityView(LoginRequiredMixin, TemplateView):
    """Displays both receipts (purchases) and invoices (sales) for the current day."""
    template_name = 'inventory/daily_activity.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()

        # Get today's receipts (Purchases)
        todays_receipts = Receipt.objects.filter(
            purchase_date=today
        ).select_related('supplier', 'created_by').order_by('created_at')

        # Get today's invoices (Sales)
        todays_invoices = Invoice.objects.filter(
            sale_date=today
        ).select_related('created_by').order_by('created_at')

        # Calculate totals
        purchase_totals = todays_receipts.aggregate(
            total_purchase_amount=Sum('total_amount'),
            receipt_count=Count('id')
        )
        sales_totals = todays_invoices.aggregate(
            total_sales_amount=Sum('total_amount'),
            invoice_count=Count('id')
        )

        context['today_date'] = today
        context['todays_receipts'] = todays_receipts
        context['todays_invoices'] = todays_invoices
        context['total_purchase_amount'] = purchase_totals.get('total_purchase_amount') or 0.00
        context['receipt_count_today'] = purchase_totals.get('receipt_count') or 0
        context['total_sales_amount'] = sales_totals.get('total_sales_amount') or 0.00
        context['invoice_count_today'] = sales_totals.get('invoice_count') or 0
        context['page_title'] = f'Activity for Today ({today.strftime("%Y-%m-%d")})'

        return context    
    

# inventory/views.py

# ... imports ...

def register(request): # <--- MAKE SURE THIS FUNCTION EXISTS
    """Handles user registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Registration successful! Welcome, {user.username}.")
            return redirect('dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = UserCreationForm()

    context = {
        'form': form,
        'page_title': 'Register New Account'
    }
    return render(request, 'registration/register.html', context)

# ... other views ...

from django.contrib.auth.forms import UserCreationForm # Import UserCreationForm
from django.contrib.auth import login, authenticate
# ... other views ...

from django.contrib.auth.forms import UserCreationForm # Import UserCreationForm
from django.contrib.auth import login, authenticate
from django.contrib.auth import login, authenticate


# inventory/views.py

# ... (keep existing imports)
from decimal import Decimal # Ensure Decimal is imported for calculations

# ... (Keep existing forms like DateRangeReportForm)
# ... (Keep existing models like InvoiceItem, Product)
# ... (Keep existing Mixins like StaffRequiredMixin)
# ... (Keep existing Views)


# --- NEW: Profit Report View ---

class ProfitReportView(StaffRequiredMixin, TemplateView):
    """
    View to display and calculate profit based on a selected date range.
    Uses GET parameters for filtering.
    """
    template_name = 'inventory/profit_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Initialize form with GET data (if any) or unbound
        form = DateRangeReportForm(self.request.GET or None)
        context['form'] = form
        context['page_title'] = 'Profit Report'

        # Initialize results
        context['start_date'] = None
        context['end_date'] = None
        context['total_revenue'] = Decimal('0.00')
        context['total_cogs'] = Decimal('0.00')
        context['total_profit'] = Decimal('0.00')
        context['items_sold'] = [] # Optional: list items contributing to profit

        # Process form if submitted via GET and valid
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            context['start_date'] = start_date
            context['end_date'] = end_date

            # Query InvoiceItems within the date range that have a product linked
            # Select related product and invoice for efficiency
            items_sold = InvoiceItem.objects.filter(
                invoice__sale_date__gte=start_date,
                invoice__sale_date__lte=end_date,
                product__isnull=False # Important: Exclude items where product might be deleted
            ).select_related('product', 'invoice')

            total_revenue = Decimal('0.00')
            total_cogs = Decimal('0.00')

            # Calculate totals by iterating (alternative to aggregate for clarity here)
            # Or use aggregate (more efficient for large datasets)
            # items_sold_agg = items_sold.aggregate(
            #    total_revenue=Sum(F('quantity') * F('unit_price'), output_field=DecimalField()),
            #    total_cogs=Sum(F('quantity') * F('product__unit_price'), output_field=DecimalField())
            # )
            # total_revenue = items_sold_agg.get('total_revenue') or Decimal('0.00')
            # total_cogs = items_sold_agg.get('total_cogs') or Decimal('0.00')

            # Iteration method (can be slower but shows individual item calc if needed)
            processed_items = []
            for item in items_sold:
                line_revenue = item.quantity * item.unit_price
                line_cogs = item.quantity * item.product.unit_price # Assumes product.unit_price is cost
                line_profit = line_revenue - line_cogs
                total_revenue += line_revenue
                total_cogs += line_cogs
                processed_items.append({
                    'item': item,
                    'line_revenue': line_revenue,
                    'line_cogs': line_cogs,
                    'line_profit': line_profit
                })


            total_profit = total_revenue - total_cogs

            # Update context with calculated results
            context['total_revenue'] = total_revenue
            context['total_cogs'] = total_cogs
            context['total_profit'] = total_profit
            context['items_sold'] = processed_items # Pass processed items if showing table
            context['results_available'] = True # Flag to show results section

        return context