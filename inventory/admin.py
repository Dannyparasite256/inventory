# inventory/admin.py

from django.contrib import admin
from django.forms import ValidationError
from .models import Category, Supplier, Product, Transaction, Receipt, ReceiptItem, Invoice, InvoiceItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone')
    search_fields = ('name', 'contact_person', 'email')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'supplier', 'quantity', 'unit_price', 'selling_price', 'reorder_level', 'updated_at')
    list_filter = ('category', 'supplier', 'updated_at')
    search_fields = ('name', 'sku', 'description')
    readonly_fields = ('quantity',) # Quantity managed by transactions
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'description', 'category', 'supplier')
        }),
        ('Stock & Pricing', {
            'fields': ('quantity', 'unit_price', 'selling_price', 'reorder_level')
        }),
    )

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('product', 'transaction_type', 'quantity', 'timestamp', 'user', 'notes')
    list_filter = ('transaction_type', 'timestamp', 'user')
    search_fields = ('product__name', 'notes')
    readonly_fields = ('timestamp',) # Set automatically

# --- Inline Admins for Receipt and Invoice Items ---

class ReceiptItemInline(admin.TabularInline):
    model = ReceiptItem
    extra = 1 # Number of empty forms to display
    autocomplete_fields = ['product'] # Requires search_fields in ProductAdmin

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    autocomplete_fields = ['product']

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'supplier', 'purchase_date', 'total_amount', 'created_by', 'created_at')
    list_filter = ('purchase_date', 'supplier', 'created_by')
    search_fields = ('receipt_number', 'supplier__name', 'notes')
    inlines = [ReceiptItemInline]
    readonly_fields = ('total_amount', 'created_at', 'updated_at') # Calculated fields
    autocomplete_fields = ['supplier'] # Requires search_fields in SupplierAdmin

    def save_formset(self, request, form, formset, change):
        """Recalculate total after saving inline formset."""
        instances = formset.save(commit=False)
        for instance in instances:
            # Ensure association with the main object if needed,
            # and link created_by if applicable to line items.
            instance.save()
        formset.save_m2m()
        # Recalculate the total after all items are saved
        if form.instance.pk:
            form.instance.calculate_total()
            form.instance.save() # Save the main object again with updated total

    def save_model(self, request, obj, form, change):
        """Assign the current user when creating a receipt."""
        if not obj.pk: # Only set created_by on initial creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # Initial total calculation might be needed here if items added immediately
        obj.calculate_total()


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer_name', 'sale_date', 'total_amount', 'created_by', 'created_at')
    list_filter = ('sale_date', 'created_by')
    search_fields = ('invoice_number', 'customer_name', 'notes')
    inlines = [InvoiceItemInline]
    readonly_fields = ('sub_total', 'tax_amount', 'discount_amount', 'total_amount', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('invoice_number', 'customer_name', 'sale_date', 'due_date', 'notes')}),
        ('Pricing', {'fields': ('tax_rate', 'discount_rate')}),
        ('Totals', {'fields': ('sub_total', 'discount_amount', 'tax_amount', 'total_amount')}),
    )

    def save_formset(self, request, form, formset, change):
        """Recalculate total after saving inline formset."""
        instances = formset.save(commit=False)
        # Need to perform stock validation here before saving items if done via admin
        try:
            for instance in instances:
                # Validate stock before saving each item if it's new
                 if not instance.pk and instance.product.quantity < instance.quantity:
                     # Raise validation error to prevent saving
                     # This basic check might not cover updates correctly in admin inlines
                     # A more robust solution might involve signals or custom formset validation
                     raise ValidationError(f"Insufficient stock for {instance.product.name}. Available: {instance.product.quantity}")
                 instance.save()
            formset.save_m2m()
            # Recalculate totals after all items are saved
            if form.instance.pk:
                 form.instance.calculate_totals()
                 form.instance.save() # Save the main object again
        except ValidationError as e:
            # Propagate the error to the admin interface
             self.message_user(request, str(e), level='ERROR')
             # Need to prevent saving if validation fails. How to cleanly do this in save_formset?
             # This might require overriding the formset's clean method.

    def save_model(self, request, obj, form, change):
        """Assign the current user when creating an invoice."""
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # Initial total calculation
        obj.calculate_totals()