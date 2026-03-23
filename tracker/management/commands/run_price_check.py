"""
management/commands/run_price_check.py

Django management command that implements Algorithm 3 from the design:
Scheduled Price Check and Alert.

Run manually:  python manage.py run_price_check
Schedule with cron (twice daily as per objective 3.3):
    0 8,20 * * * /path/to/venv/bin/python manage.py run_price_check
"""

import time
import random
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from tracker.models import ProductRetailer, UserTrackedItem, PriceHistory, UserProfile
from tracker.scraper import scrape_product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrapes prices for all tracked products and sends alerts if needed.'

    def handle(self, *args, **options):
        self.stdout.write('Starting scheduled price check...')
        self.run_price_check()
        self.stdout.write(self.style.SUCCESS('Price check complete.'))

    def run_price_check(self):
        """
        Algorithm 3: ScheduledPriceCheck
        Gets all active tracked products and checks each one.
        """
        # Get every unique product/retailer pair that at least one user is tracking.
        tracked_pairs = set(
            UserTrackedItem.objects.filter(is_active=True)
            .values_list('product_id', 'retailer_id')
        )
        active_prs = ProductRetailer.objects.filter(is_active=True).select_related(
            'product', 'retailer'
        )
        active_prs = [
            pr for pr in active_prs
            if (pr.product_id, pr.retailer_id) in tracked_pairs
        ]

        self.stdout.write(f'Found {len(active_prs)} products to check.')

        for pr in active_prs:
            self.stdout.write(f"Checking: {pr.product.product_name}")

            scraped = scrape_product(pr.product_url)

            if scraped is not None:
                # Save price record (Algorithm 3: savePriceHistory)
                PriceHistory.objects.create(
                    product=pr.product,
                    retailer=pr.retailer,
                    price=scraped.price,
                    in_stock=scraped.in_stock,
                )
                # Update the last checked timestamp
                pr.last_checked = timezone.now()
                pr.save()

                self.stdout.write(f"  -> £{scraped.price:.2f}")
            else:
                logger.error(f"Scraping failed for {pr.product_url}")
                self.stdout.write(f"  -> FAILED")

            # Random polite delay between requests (3-8 seconds)
            time.sleep(random.uniform(3, 8))

        # After updating all prices, check who needs an alert
        self.send_price_alerts()

    def send_price_alerts(self):
        """
        Algorithm 3: sendPriceAlert
        Finds all tracked items where the latest price is at or below
        the user's desired price, and sends an email.
        """
        active_tracked = UserTrackedItem.objects.filter(
            is_active=True,
            desired_price__isnull=False,
            user__is_active=True
        ).select_related('user', 'product', 'retailer')

        for tracked in active_tracked:
            latest = PriceHistory.objects.filter(
                product=tracked.product,
                retailer=tracked.retailer
            ).order_by('-timestamp').first()

            if not latest:
                continue

            # Algorithm 3: IF currentPrice <= product.desiredPrice
            if latest.price <= tracked.desired_price:
                self.send_alert_notifications(tracked, latest.price)

    def send_alert_notifications(self, tracked, current_price):
        """Prints alert messages to the console."""
        product_url = ProductRetailer.objects.get(
            product=tracked.product,
            retailer=tracked.retailer
        ).product_url

        subject = f"Price Alert: {tracked.product.product_name} is now £{current_price:.2f}!"

        message = (
            f"Great news!\n\n"
            f"{tracked.product.product_name} on {tracked.retailer.retailer_name} "
            f"has dropped to £{current_price:.2f}.\n"
            f"Your target price was £{tracked.desired_price:.2f}.\n\n"
            f"Buy it here: {product_url}\n\n"
            f"-- PriceTracker"
        )

        self.stdout.write(
            f"EMAIL: would send {tracked.product.product_name} alert to {tracked.user.email}."
        )
        self.stdout.write(f"EMAIL CONTENT:\nSubject: {subject}\n{message}")
        logger.info(
            f"Email alert prepared for {tracked.user.email}: "
            f"{tracked.product.product_name} at £{current_price}"
        )

        profile = UserProfile.objects.filter(user=tracked.user).first()
        if profile and profile.user_num:
            self.stdout.write(
                f"SMS: would send {tracked.product.product_name} alert to {profile.user_num}."
            )
