from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from tracker.models import PriceHistory, Product, ProductRetailer, Retailer, UserTrackedItem
from tracker.scraper import ScrapedProduct


class AddProductViewTests(TestCase):
    def setUp(self):
        self.retailer = Retailer.objects.create(
            retailer_name='Amazon',
            base_url='https://www.amazon.co.uk',
            is_active=True,
        )
        self.user_one = User.objects.create_user(
            username='one@example.com',
            email='one@example.com',
            password='testpass123',
        )
        self.user_two = User.objects.create_user(
            username='two@example.com',
            email='two@example.com',
            password='testpass123',
        )
        self.url = reverse('add_product')
        self.product_url = 'https://www.amazon.co.uk/dp/B000TEST?ref_=abc'

    def _login(self, user):
        self.client.force_login(user)

    @patch('tracker.views.scrape_product')
    def test_different_users_can_track_same_product(self, mock_scrape):
        mock_scrape.return_value = ScrapedProduct('Shared Product', 19.99, 'https://img', True)

        self._login(self.user_one)
        response_one = self.client.post(self.url, {
            'product_url': self.product_url,
            'desired_price': '18.00',
        })
        self.assertRedirects(response_one, reverse('dashboard'))

        self.client.logout()
        self._login(self.user_two)
        response_two = self.client.post(self.url, {
            'product_url': 'https://www.amazon.co.uk/dp/B000TEST/?ref_=different',
            'desired_price': '17.00',
        })
        self.assertRedirects(response_two, reverse('dashboard'))

        tracked_items = UserTrackedItem.objects.filter(product__product_name='Shared Product')
        self.assertEqual(tracked_items.count(), 2)
        self.assertSetEqual(set(tracked_items.values_list('user__email', flat=True)), {
            'one@example.com',
            'two@example.com',
        })
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductRetailer.objects.count(), 1)
        self.assertEqual(PriceHistory.objects.count(), 1)

    @patch('tracker.views.scrape_product')
    def test_readding_inactive_item_reactivates_existing_track(self, mock_scrape):
        mock_scrape.return_value = ScrapedProduct('Reactivated Product', 19.99, 'https://img', True)

        self._login(self.user_one)
        self.client.post(self.url, {
            'product_url': self.product_url,
            'desired_price': '18.00',
        })
        tracked_item = UserTrackedItem.objects.get(user=self.user_one)
        tracked_item.is_active = False
        tracked_item.save(update_fields=['is_active'])

        response = self.client.post(self.url, {
            'product_url': self.product_url,
            'desired_price': '16.00',
        }, follow=True)

        tracked_item.refresh_from_db()
        self.assertTrue(tracked_item.is_active)
        self.assertEqual(tracked_item.desired_price, Decimal('16.00'))
        self.assertEqual(UserTrackedItem.objects.filter(user=self.user_one).count(), 1)
        messages = [message.message for message in get_messages(response.wsgi_request)]
        self.assertIn('Product added to your tracking list!', messages)

    @patch('tracker.views.scrape_product')
    def test_duplicate_urls_for_same_product_do_not_create_duplicates(self, mock_scrape):
        mock_scrape.return_value = ScrapedProduct('Canonical Product', 29.99, 'https://img', True)

        self._login(self.user_one)
        response_one = self.client.post(self.url, {
            'product_url': 'https://www.amazon.co.uk/dp/B000TEST/?tag=abc',
            'desired_price': '28.00',
        })
        self.assertRedirects(response_one, reverse('dashboard'))

        response_two = self.client.post(self.url, {
            'product_url': 'https://www.amazon.co.uk/dp/B000TEST?tag=xyz#details',
            'desired_price': '27.00',
        }, follow=True)
        self.assertRedirects(response_two, reverse('dashboard'))

        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductRetailer.objects.count(), 1)
        self.assertEqual(UserTrackedItem.objects.count(), 1)
        messages = [message.message for message in get_messages(response_two.wsgi_request)]
        self.assertIn('You are already tracking that product.', messages)
