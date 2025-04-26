# inventory/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db.models import Sum, F, ExpressionWrapper, DecimalField

class Category(models.Model):
    """Model representing a product category."""
    name = models.CharField(max_length=100, unique=True, help_text="Enter product category (e.g. Electronics)")
    description = models.TextField(blank=True, null=True, help_text="Optional description")

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('category-list') # Redirect to list view after create/update

class Supplier(models.Model):
    """Model representing a supplier."""
    name = models.CharField(max_length=200, unique=True)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('supplier-list')

class Product(models.Model):
    """Model representing a product in the inventory."""
    name = models.CharField(max_length=200, help_text="Product name")
    description = models.TextField(blank=True, null=True, help_text="Product description")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True, help_text="Stock Keeping Unit")
    quantity = models.PositiveIntegerField(default=0, help_text="Current stock level")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per unit (purchase price)")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Selling price per unit")
    reorder_level = models.PositiveIntegerField(default=10, help_text="Minimum stock level before reordering")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.sku or 'No SKU'})"

    def get_absolute_url(self):
        return reverse('product-detail', args=[str(self.id)])

    @property
    def is_below_reorder_level(self):
        return self.quantity <= self.reorder_level

    def update_stock(self, quantity_change):
        """Updates stock level. Positive for stock in, negative for stock out."""
        if self.quantity + quantity_change < 0:
            raise ValidationError(f"Cannot reduce stock below zero for {self.name}.")
        self.quantity = F('quantity') + quantity_change
        self.save(update_fields=['quantity'])
        self.refresh_from_db() # Ensure the instance reflects the updated database value

class Transaction(models.Model):
    """Model representing an inventory transaction (stock in/out)."""
    TRANSACTION_TYPES = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
        ('ADJ', 'Adjustment'), # For stock counts, corrections
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES)
    quantity = models.PositiveIntegerField()
    timestamp = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who performed the transaction")
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_transaction_type_display()} - {self.product.name} ({self.quantity}) on {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs) # Save the transaction first
        # Update product stock only for new transactions to avoid double counting on edits
        if is_new:
            if self.transaction_type == 'IN' or self.transaction_type == 'ADJ': # Assuming Adjustment adds stock initially
                self.product.update_stock(self.quantity)
            elif self.transaction_type == 'OUT':
                self.product.update_stock(-self.quantity)
            # If you need complex logic for ADJ (e.g., setting absolute value), adjust here.

# --- Receipts (Purchases from Suppliers) ---

class Receipt(models.Model):
    """Represents a purchase receipt from a supplier."""
    receipt_number = models.CharField(max_length=50, unique=True, help_text="Unique receipt identifier")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, related_name='receipts')
    purchase_date = models.DateField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_receipts')

    class Meta:
        ordering = ['-purchase_date', '-created_at']

    def __str__(self):
        return f"Receipt {self.receipt_number} from {self.supplier.name if self.supplier else 'N/A'}"

    def get_absolute_url(self):
        return reverse('receipt-detail', args=[str(self.id)])

    def calculate_total(self):
        """Calculates the total amount based on receipt items."""
        total = self.items.aggregate(
            total=Sum(ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField()))
        )['total'] or 0.00
        self.total_amount = total
        self.save(update_fields=['total_amount'])

class ReceiptItem(models.Model):
    """Represents a line item on a purchase receipt."""
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Purchase price per unit for this receipt")

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ {self.unit_price}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new: # Only trigger stock update and total calculation on creation
             # Create a corresponding 'Stock In' transaction
            Transaction.objects.create(
                product=self.product,
                transaction_type='IN',
                quantity=self.quantity,
                user=self.receipt.created_by, # Associate with user who created receipt
                notes=f"Stock in via Receipt {self.receipt.receipt_number}"
            )
        # Recalculate receipt total after item save/update
        # Consider moving this logic to a signal or view if performance becomes an issue
        if self.receipt:
            self.receipt.calculate_total()

    def delete(self, *args, **kwargs):
        # Optional: Reverse the stock transaction if a receipt item is deleted
        # This requires careful consideration of your business logic
        # For simplicity, we might disallow deletion or require manual adjustment.
        # Transaction.objects.create(
        #     product=self.product,
        #     transaction_type='ADJ', # Or a specific 'RECEIPT_DELETE' type
        #     quantity=-self.quantity, # Negative quantity to reverse
        #     user= ? # Who deleted it? Needs request context or fixed user
        #     notes=f"Stock adjustment due to deletion of item from Receipt {self.receipt.receipt_number}"
        # )
        super().delete(*args, **kwargs)
        if self.receipt:
            self.receipt.calculate_total() # Recalculate after delete

# --- Invoices (Sales to Customers) ---

class Invoice(models.Model):
    """Represents a sales invoice to a customer."""
    invoice_number = models.CharField(max_length=50, unique=True, help_text="Unique invoice identifier")
    customer_name = models.CharField(max_length=200, blank=True, null=True) # Simple customer name for now
    sale_date = models.DateField(default=timezone.now)
    due_date = models.DateField(blank=True, null=True)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Tax rate in percentage (e.g., 10 for 10%)")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, help_text="Discount rate in percentage (e.g., 5 for 5%)")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_invoices')

    class Meta:
        ordering = ['-sale_date', '-created_at']

    def __str__(self):
        return f"Invoice {self.invoice_number} for {self.customer_name or 'N/A'}"

    def get_absolute_url(self):
        return reverse('invoice-detail', args=[str(self.id)])

    def calculate_totals(self):
        """Calculates sub_total, tax, discount, and total amount based on invoice items."""
        sub_total_calc = self.items.aggregate(
            total=Sum(ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField()))
        )['total'] or 0.00

        self.sub_total = sub_total_calc
        self.discount_amount = (self.sub_total * self.discount_rate) / 100
        amount_after_discount = self.sub_total - self.discount_amount
        self.tax_amount = (amount_after_discount * self.tax_rate) / 100
        self.total_amount = amount_after_discount + self.tax_amount

        self.save(update_fields=['sub_total', 'tax_amount', 'discount_amount', 'total_amount'])

class InvoiceItem(models.Model):
    """Represents a line item on a sales invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Selling price per unit for this invoice")

    def __str__(self):
        return f"{self.quantity} x {self.product.name} @ {self.unit_price}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        # Ensure unit price defaults to product's selling price if not provided? Maybe handle in form.
        # Here we assume unit_price is set correctly before saving.

        # Validate stock before saving
        if is_new:
             if self.product.quantity < self.quantity:
                 raise ValidationError(f"Not enough stock for {self.product.name}. Available: {self.product.quantity}")

        super().save(*args, **kwargs)

        if is_new: # Only trigger stock update and total calculation on creation
            # Create a corresponding 'Stock Out' transaction
            Transaction.objects.create(
                product=self.product,
                transaction_type='OUT',
                quantity=self.quantity,
                user=self.invoice.created_by, # Associate with user who created invoice
                notes=f"Stock out via Invoice {self.invoice.invoice_number}"
            )

        # Recalculate invoice totals after item save/update
        if self.invoice:
            self.invoice.calculate_totals()

    def delete(self, *args, **kwargs):
        # Optional: Reverse the stock transaction if an invoice item is deleted
        # Transaction.objects.create(
        #     product=self.product,
        #     transaction_type='IN', # Stock comes back in
        #     quantity=self.quantity,
        #     user= ? # Who deleted it? Needs request context or fixed user
        #     notes=f"Stock adjustment due to deletion of item from Invoice {self.invoice.invoice_number}"
        # )
        super().delete(*args, **kwargs)
        if self.invoice:
            self.invoice.calculate_totals() # Recalculate after delete
