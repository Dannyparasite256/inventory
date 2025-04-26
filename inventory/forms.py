from pyexpat.errors import messages
from django import forms
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import redirect
from weasyprint import HTML
from .models import Category, Supplier, Product, Receipt, ReceiptItem, Invoice, InvoiceItem
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid # For generating unique numbers

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'email', 'phone', 'address']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'supplier', 'sku',
                  'unit_price', 'selling_price', 'reorder_level'] # Exclude 'quantity' - managed by transactions
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_selling_price(self):
        selling_price = self.cleaned_data.get('selling_price')
        unit_price = self.cleaned_data.get('unit_price')
        if selling_price is not None and unit_price is not None and selling_price < unit_price:
            raise ValidationError("Selling price cannot be less than the unit (cost) price.")
        return selling_price

class ProductFilterForm(forms.Form):
    """Form for filtering products in the list view."""
    name = forms.CharField(required=False, label="Product Name", widget=forms.TextInput(attrs={'placeholder': 'Search by name...'}))
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label="All Categories")
    supplier = forms.ModelChoiceField(queryset=Supplier.objects.all(), required=False, empty_label="All Suppliers")
    below_reorder = forms.BooleanField(required=False, label="Below Reorder Level")

# --- Receipt Forms ---

class ReceiptForm(forms.ModelForm):
    purchase_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now().date())

    class Meta:
        model = Receipt
        fields = ['receipt_number', 'supplier', 'purchase_date', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-generate receipt number if creating new
        if not self.instance.pk and not self.initial.get('receipt_number'):
             self.initial['receipt_number'] = f"REC-{uuid.uuid4().hex[:8].upper()}" # Example auto-numbering

class ReceiptItemForm(forms.ModelForm):
    class Meta:
        model = ReceiptItem
        fields = ['product', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.order_by('name') # Order product dropdown
        # Optionally set initial unit price from product cost price
        # This requires passing the product instance or handling in the view/template
        # if 'instance' in kwargs and kwargs['instance'] and kwargs['instance'].product:
        #     self.initial['unit_price'] = kwargs['instance'].product.unit_price


# Inline Formset for Receipt Items
ReceiptItemFormSet = inlineformset_factory(
    Receipt,                  # Parent model
    ReceiptItem,              # Inline model
    form=ReceiptItemForm,     # Form for inline model
    extra=1,                  # Number of empty forms
    can_delete=True,          # Allow deletion of items
    can_delete_extra=True     # Allow deletion of newly added (unsaved) extra forms
)


# --- Invoice Forms ---

class InvoiceForm(forms.ModelForm):
    sale_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), initial=timezone.now().date())
    due_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)

    class Meta:
        model = Invoice
        fields = ['invoice_number', 'customer_name', 'sale_date', 'due_date',
                  'tax_rate', 'discount_rate', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-generate invoice number if creating new
        if not self.instance.pk and not self.initial.get('invoice_number'):
             self.initial['invoice_number'] = f"INV-{uuid.uuid4().hex[:8].upper()}" # Example auto-numbering

# inventory/forms.py

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'quantity', 'unit_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.order_by('name')

        # --- MODIFIED CHECK ---
        # Only try to access product details if the instance exists,
        # has been saved (has a pk), and actually has a product linked.
        if self.instance and self.instance.pk and self.instance.product:
             # Only set initial price if not already set (e.g., from POST data)
             # and if the instance is a saved one with a product.
             if not self.initial.get('unit_price'):
                 self.initial['unit_price'] = self.instance.product.selling_price
        # --- END MODIFIED CHECK ---

    def clean_quantity(self):
        # ... (keep existing clean_quantity method) ...
        quantity = self.cleaned_data.get('quantity')
        product = self.cleaned_data.get('product')
        instance = getattr(self, 'instance', None)

        if product and quantity is not None:
            current_stock = product.quantity
            original_quantity = 0
            if instance and instance.pk:
                original_quantity = instance.quantity

            quantity_change = quantity - original_quantity

            if quantity_change > current_stock:
                 raise ValidationError(f"Not enough stock for {product.name}. "
                                     f"Available: {current_stock}. Requested Change: {quantity_change}")
        return quantity

# Inline Formset for Invoice Items
InvoiceItemFormSet = inlineformset_factory(
    Invoice,                  # Parent model
    InvoiceItem,              # Inline model
    form=InvoiceItemForm,     # Form for inline model
    extra=1,                  # Number of empty forms
    can_delete=True,
    can_delete_extra=True
)

# --- Report Forms ---
class DateRangeReportForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=True)

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            raise ValidationError("End date cannot be earlier than start date.")

        return cleaned_data
    

    # inventory/forms.py
# ... (keep existing imports and forms)
from django import forms
from django.utils import timezone

# ... (CategoryForm, SupplierForm, ProductForm, etc.)

class DailySalesReportForm(forms.Form):
    """Form to select a date for the daily sales report."""
    report_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        initial=timezone.now().date(), # Default to today
        label="Report Date"
    )
