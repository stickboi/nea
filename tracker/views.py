"""
views.py
All views for the PriceTracker app.
Each view corresponds to a URL and renders a template.
"""

import json
import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Min, Max, Avg
from django.core.mail import send_mail
from django.conf import settings

from .models import (
    UserProfile, Retailer, Product, ProductRetailer,
    UserTrackedItem, PriceHistory,
)
from .forms import (
    RegisterForm, LoginForm, AddProductForm,
    UpdateDesiredPriceForm, ProfileForm,
)
from .scraper import scrape_product, is_supported_url

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Authentication
# ──────────────────────────────────────────────────────────────

def index(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')


def register_view(request):
    """Algorithm 1 - User Registration."""
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            email    = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user_num = form.cleaned_data.get('user_num')

            # Create Django user - username is the email address
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password
            )
            # Create the associated profile for phone number
            UserProfile.objects.create(user=user, user_num=user_num)

            # Send a welcome email (non-critical)
            try:
                send_mail(
                    subject='Welcome to PriceTracker',
                    message=(
                        'Welcome to PriceTracker!\n\n'
                        'You can now add products to your watchlist and we will '
                        'alert you when the price drops below your target.\n\n'
                        'Happy saving!'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )
            except Exception:
                pass

            messages.success(request, 'Registration successful! Please log in.')
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'tracker/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Incorrect email or password.')
    else:
        form = LoginForm()

    return render(request, 'tracker/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ──────────────────────────────────────────────────────────────
# Dashboard
# ──────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """
    Main dashboard - shows all products the user is tracking
    with current price and whether it is below their target.
    """
    tracked_items = UserTrackedItem.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('product', 'retailer')

    product_urls = {
        (product_id, retailer_id): product_url
        for product_id, retailer_id, product_url in ProductRetailer.objects.filter(
            product_id__in=tracked_items.values_list('product_id', flat=True),
            retailer_id__in=tracked_items.values_list('retailer_id', flat=True),
            is_active=True,
        ).values_list('product_id', 'retailer_id', 'product_url')
    }

    # Build a list of dicts with everything the template needs
    items = []
    for tracked in tracked_items:
        # Get the most recent price record for this product/retailer pair
        latest_price = PriceHistory.objects.filter(
            product=tracked.product,
            retailer=tracked.retailer
        ).order_by('-timestamp').first()

        current_price = latest_price.price if latest_price else None
        in_stock      = latest_price.in_stock if latest_price else True
        last_checked  = latest_price.timestamp if latest_price else None

        # Green/red indicator - is the current price at or below the target?
        below_target = False
        if current_price is not None and tracked.desired_price is not None:
            below_target = current_price <= tracked.desired_price

        items.append({
            'product':       tracked.product,
            'retailer':      tracked.retailer,
            'tracked':       tracked,
            'product_url':   product_urls.get((tracked.product_id, tracked.retailer_id), ''),
            'current_price': current_price,
            'in_stock':      in_stock,
            'last_checked':  last_checked,
            'below_target':  below_target,
        })

    return render(request, 'tracker/dashboard.html', {'items': items})


# ──────────────────────────────────────────────────────────────
# Add product
# ──────────────────────────────────────────────────────────────

@login_required
def add_product(request):
    """Algorithm 2 - AddProductToTrack."""
    if request.method == 'POST':
        form = AddProductForm(request.POST)
        if form.is_valid():
            url           = form.cleaned_data['product_url']
            desired_price = form.cleaned_data.get('desired_price')

            # Identify retailer from the URL
            retailer = None
            for r in Retailer.objects.filter(is_active=True):
                if r.base_url.replace('https://www.', '') in url:
                    retailer = r
                    break

            if not retailer:
                messages.error(request, 'Could not identify the retailer from that URL.')
                return render(request, 'tracker/add_product.html', {'form': form})

            # Check if this URL already exists in the database
            existing_pr = ProductRetailer.objects.filter(product_url=url).first()

            if existing_pr:
                product = existing_pr.product
            else:
                # Scrape the product page for the first time
                scraped = scrape_product(url)

                if scraped is None:
                    messages.error(
                        request,
                        'Could not retrieve product information from that page. '
                        'The page layout may have changed or the item is unavailable.'
                    )
                    return render(request, 'tracker/add_product.html', {'form': form})

                # Create the Product record
                product = Product.objects.create(
                    product_name=scraped.name,
                    image_url=scraped.image_url or '',
                )
                # Link it to the retailer
                ProductRetailer.objects.create(
                    product=product,
                    retailer=retailer,
                    product_url=url,
                    last_checked=timezone.now(),
                )
                # Save the first price record straight away
                PriceHistory.objects.create(
                    product=product,
                    retailer=retailer,
                    price=scraped.price,
                    in_stock=scraped.in_stock,
                )

            # Add to the user's tracking list
            _, created = UserTrackedItem.objects.get_or_create(
                user=request.user,
                product=product,
                retailer=retailer,
                defaults={'desired_price': desired_price, 'is_active': True}
            )

            if created:
                messages.success(request, 'Product added to your tracking list!')
            else:
                messages.warning(request, 'You are already tracking that product.')

            return redirect('dashboard')
    else:
        form = AddProductForm()

    return render(request, 'tracker/add_product.html', {'form': form})


# ──────────────────────────────────────────────────────────────
# Remove product
# ──────────────────────────────────────────────────────────────

@login_required
def remove_product(request, tracked_id):
    """Soft-deletes a tracking entry (sets is_active=False)."""
    tracked = get_object_or_404(UserTrackedItem, id=tracked_id, user=request.user)
    tracked.is_active = False
    tracked.save()
    messages.info(request, 'Product removed from your tracking list.')
    return redirect('dashboard')


# ──────────────────────────────────────────────────────────────
# Price history
# ──────────────────────────────────────────────────────────────

@login_required
def price_history(request, tracked_id):
    """
    Algorithm 4 - GeneratePriceHistoryData.
    Shows a Chart.js line graph of the product's price over time.
    """
    tracked = get_object_or_404(
        UserTrackedItem, id=tracked_id, user=request.user, is_active=True
    )

    days = int(request.GET.get('range', 30))
    since = timezone.now() - timedelta(days=days)

    # Get price records grouped by day for the chart
    history_qs = (
        PriceHistory.objects
        .filter(product=tracked.product, retailer=tracked.retailer, timestamp__gte=since)
        .order_by('timestamp')
    )

    # Algorithm 4: build the chart data structure
    labels = []
    prices = []
    for record in history_qs:
        labels.append(record.timestamp.strftime('%Y-%m-%d'))
        prices.append(float(record.price))

    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Price (£)',
            'data': prices,
            'borderColor': 'rgb(75, 192, 192)',
            'backgroundColor': 'rgba(75, 192, 192, 0.1)',
            'tension': 0.1,
            'fill': True,
        }]
    }

    # Quick stats
    stats = history_qs.aggregate(
        min_price=Min('price'),
        max_price=Max('price'),
        avg_price=Avg('price'),
    )

    # Current price (most recent)
    latest = history_qs.last()
    current_price = latest.price if latest else None

    below_target = False
    if current_price is not None and tracked.desired_price is not None:
        below_target = current_price <= tracked.desired_price

    context = {
        'tracked':       tracked,
        'chart_data':    json.dumps(chart_data),
        'stats':         stats,
        'current_price': current_price,
        'below_target':  below_target,
        'days':          days,
    }
    return render(request, 'tracker/price_history.html', context)


# ──────────────────────────────────────────────────────────────
# Update desired price (AJAX)
# ──────────────────────────────────────────────────────────────

@login_required
def update_desired_price(request):
    """AJAX endpoint - updates the user's target price for a tracked item."""
    if request.method == 'POST':
        form = UpdateDesiredPriceForm(request.POST)
        if form.is_valid():
            tracked_id    = form.cleaned_data['product_id']   # reusing field name
            desired_price = form.cleaned_data['desired_price']

            try:
                tracked = UserTrackedItem.objects.get(
                    id=tracked_id, user=request.user, is_active=True
                )
                tracked.desired_price = desired_price
                tracked.save()
                return JsonResponse({
                    'success': True,
                    'message': f'Target price updated to £{desired_price:.2f}'
                })
            except UserTrackedItem.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Item not found.'})

    return JsonResponse({'success': False, 'message': 'Invalid request.'})


# ──────────────────────────────────────────────────────────────
# Profile
# ──────────────────────────────────────────────────────────────

@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST)
        if form.is_valid():
            profile_obj.user_num = form.cleaned_data['user_num']
            profile_obj.save()
            messages.success(request, 'Profile updated.')
            return redirect('profile')
    else:
        form = ProfileForm(initial={'user_num': profile_obj.user_num or ''})

    tracked_count = UserTrackedItem.objects.filter(
        user=request.user, is_active=True
    ).count()
    price_checks = PriceHistory.objects.filter(
        product__usertrackeditem__user=request.user
    ).count()

    return render(request, 'tracker/profile.html', {
        'form':          form,
        'user':          request.user,
        'profile':       profile_obj,
        'tracked_count': tracked_count,
        'price_checks':  price_checks,
    })
