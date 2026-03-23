from django.db import models
from django.contrib.auth.models import User  # Django's built-in user model


class UserProfile(models.Model):
    """
    Extends Django's built-in User model with a phone number
    for SMS alerts, as specified in the data dictionary.
    """
    user     = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    user_num = models.CharField(max_length=15, blank=True, null=True)  # 11-digit phone number

    def __str__(self):
        return f"Profile({self.user.email})"


class Retailer(models.Model):
    """
    Supported online retailers. Pre-populated via a data migration.
    Maps to the Retailers table in the design.
    """
    retailer_name = models.CharField(max_length=100)
    base_url      = models.CharField(max_length=255)
    is_active     = models.BooleanField(default=True)

    def __str__(self):
        return self.retailer_name


class Product(models.Model):
    """
    One row per unique product. Maps to the Products table in the design.
    """
    product_name = models.CharField(max_length=255)
    image_url    = models.CharField(max_length=500, blank=True, null=True)
    description  = models.TextField(blank=True)
    category     = models.CharField(max_length=100, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.product_name


class ProductRetailer(models.Model):
    """
    Junction table linking a product to a retailer with the specific URL.
    Maps to the ProductRetailer table in the design (composite PK).
    """
    product     = models.ForeignKey(Product, on_delete=models.CASCADE)
    retailer    = models.ForeignKey(Retailer, on_delete=models.CASCADE)
    product_url = models.CharField(max_length=500, unique=True)
    last_checked = models.DateTimeField(blank=True, null=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        unique_together = ('product', 'retailer')

    def __str__(self):
        return f"{self.product.product_name} @ {self.retailer.retailer_name}"


class UserTrackedItem(models.Model):
    """
    Records which users are tracking which product/retailer combinations,
    and at what desired (target) price. Maps to UserTrackedItems in the design.
    """
    user          = models.ForeignKey(User, on_delete=models.CASCADE)
    product       = models.ForeignKey(Product, on_delete=models.CASCADE)
    retailer      = models.ForeignKey(Retailer, on_delete=models.CASCADE)
    desired_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    date_added    = models.DateTimeField(auto_now_add=True)
    is_active     = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'product', 'retailer')

    def __str__(self):
        return f"{self.user.email} tracking {self.product.product_name}"


class PriceHistory(models.Model):
    """
    Every price check result. Builds up over time to create the history
    chart. Maps to PriceHistory in the design.
    """
    product    = models.ForeignKey(Product, on_delete=models.CASCADE)
    retailer   = models.ForeignKey(Retailer, on_delete=models.CASCADE)
    price      = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp  = models.DateTimeField(auto_now_add=True)
    in_stock   = models.BooleanField(default=True)
    currency   = models.CharField(max_length=3, default='GBP')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.product.product_name}: £{self.price} at {self.timestamp:%Y-%m-%d %H:%M}"

