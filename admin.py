from django.contrib import admin
from .models import UserProfile, Retailer, Product, ProductRetailer, UserTrackedItem, PriceHistory


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_num')
    search_fields = ('user__email',)


@admin.register(Retailer)
class RetailerAdmin(admin.ModelAdmin):
    list_display = ('retailer_name', 'base_url', 'is_active')
    list_editable = ('is_active',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'category', 'created_at')
    search_fields = ('product_name',)


@admin.register(ProductRetailer)
class ProductRetailerAdmin(admin.ModelAdmin):
    list_display = ('product', 'retailer', 'product_url', 'last_checked', 'is_active')
    list_filter = ('retailer', 'is_active')
    search_fields = ('product__product_name', 'product_url')


@admin.register(UserTrackedItem)
class UserTrackedItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'retailer', 'desired_price', 'date_added', 'is_active')
    list_filter = ('retailer', 'is_active')
    search_fields = ('user__email', 'product__product_name')


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'retailer', 'price', 'timestamp', 'in_stock', 'currency')
    list_filter = ('retailer', 'in_stock', 'currency')
    search_fields = ('product__product_name',)
    readonly_fields = ('timestamp',)

