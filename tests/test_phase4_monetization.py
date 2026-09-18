"""
Phase 4 Integration Test Suite — Post-Auction Monetization, Settlement,
Contact Unlock & User Dashboards.

Verifies strict adherence to:
- .antigravityrules (Rule 4: Masked Contact Protection)
- PROJECT_BLUEPRINT.md (§4.4 Post-Auction Monetization Engine & §5 Monetization Model)
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User, SellerProfile
from products.models import Product
from auctions.models import Auction
from billing.models import Transaction


class Phase4MonetizationIntegrationTests(APITestCase):
    """
    Complete integration test suite for Phase 4.
    Covers the full test matrix:
    - Fixture Setup (Sellers, Buyer, Intruder, Products, Auctions)
    - Scenario A: Security, Permissions & Data Masking (Rule 4)
    - Scenario B: Path B — Pay-As-You-Sell (Standard 5% Fee & Idempotency)
    - Scenario C: Path A — Premium GMV Subscriber (Allowance Consumption)
    - Scenario D: Dashboard View Response Integrity (Seller & Buyer Dashboards)
    """

    def setUp(self):
        """1. Setup Test Fixtures as specified in test matrix."""
        # User 1: seller_standard (Individual Seller, is_premium=False)
        self.seller_standard = User.objects.create_user(
            username='seller_standard',
            email='seller_standard@test.com',
            password='Password123!',
            phone='01700000001',
            role=User.Role.INDIVIDUAL_SELLER,
            is_verified=True,
            full_name='Standard Seller User',
        )
        self.profile_standard = SellerProfile.objects.create(
            user=self.seller_standard,
            business_name='Standard Crafts',
            is_premium=False,
            monthly_gmv_allowance=Decimal('0.00'),
            used_gmv=Decimal('0.00'),
        )

        # User 2: seller_premium (Business Seller, is_premium=True, GMV=200,000)
        self.seller_premium = User.objects.create_user(
            username='seller_premium',
            email='seller_premium@test.com',
            password='Password123!',
            phone='01700000002',
            role=User.Role.BUSINESS_SELLER,
            is_verified=True,
            full_name='Premium Tech Store',
        )
        self.profile_premium = SellerProfile.objects.create(
            user=self.seller_premium,
            business_name='Premium Electronics BD',
            is_premium=True,
            monthly_gmv_allowance=Decimal('200000.00'),
            used_gmv=Decimal('0.00'),
            billing_cycle_end=timezone.now() + timedelta(days=30),
        )

        # User 3: buyer_winner
        self.buyer_winner = User.objects.create_user(
            username='buyer_winner',
            email='buyer_winner@test.com',
            password='Password123!',
            phone='01712345678',
            role=User.Role.BUYER,
            is_verified=True,
            full_name='Rahim Uddin',
            shipping_address='House 42, Road 11, Banani, Dhaka',
        )

        # User 4: intruder (unauthorized random user)
        self.intruder = User.objects.create_user(
            username='intruder',
            email='intruder@test.com',
            password='Password123!',
            phone='01700000004',
            role=User.Role.BUYER,
            is_verified=True,
            full_name='Intruder User',
        )

        # Product 1 owned by seller_standard
        self.product_1 = Product.objects.create(
            seller=self.seller_standard,
            title='Vintage Mechanical Keyboard',
            category='Electronics',
            condition=Product.Condition.USED,
            description='Authentic mechanical keyboard in great condition.',
        )

        # Product 2 owned by seller_premium
        self.product_2 = Product.objects.create(
            seller=self.seller_premium,
            title='MacBook Air M2 16GB',
            category='Computers',
            condition=Product.Condition.LIKE_NEW,
            description='Pristine condition MacBook Air.',
        )

        # Product 3 owned by seller_standard (for invalid state test)
        self.product_3 = Product.objects.create(
            seller=self.seller_standard,
            title='Wireless Noise-Canceling Headphones',
            category='Audio',
            condition=Product.Condition.USED,
            description='Headphones with active noise cancellation.',
        )

        # Auction 1: current_bid=10000.00, winner=buyer_winner, status='READY_TO_SHIP'
        self.auction_1 = Auction.objects.create(
            product=self.product_1,
            starting_bid=Decimal('5000.00'),
            current_bid=Decimal('10000.00'),
            bid_increment=Decimal('500.00'),
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            winner=self.buyer_winner,
            status=Auction.Status.READY_TO_SHIP,
        )

        # Auction 2: current_bid=25000.00, winner=buyer_winner, status='READY_TO_SHIP'
        self.auction_2 = Auction.objects.create(
            product=self.product_2,
            starting_bid=Decimal('15000.00'),
            current_bid=Decimal('25000.00'),
            bid_increment=Decimal('1000.00'),
            start_time=timezone.now() - timedelta(hours=3),
            end_time=timezone.now() - timedelta(hours=1),
            winner=self.buyer_winner,
            status=Auction.Status.READY_TO_SHIP,
        )

        # Auction 3 (Invalid state): current_bid=5000.00, status='LIVE'
        self.auction_3 = Auction.objects.create(
            product=self.product_3,
            starting_bid=Decimal('4000.00'),
            current_bid=Decimal('5000.00'),
            bid_increment=Decimal('500.00'),
            start_time=timezone.now() - timedelta(minutes=30),
            end_time=timezone.now() + timedelta(hours=1),
            winner=None,
            status=Auction.Status.LIVE,
        )

    def test_scenario_a_security_permissions_and_data_masking(self):
        """
        Scenario A: Security, Permissions & Data Masking (Rule 4).
        - Assert that fetching Auction 1 details before settlement DOES NOT leak phone or address.
        - Attempt to call unlock-buyer on Auction 1 using intruder credentials -> HTTP 403 Forbidden.
        - Attempt to call unlock-buyer on Auction 3 (status LIVE) -> HTTP 400 Bad Request.
        """
        # 1. Assert public auction room view does NOT leak winner's phone or address
        self.client.force_authenticate(user=self.intruder)
        resp_room = self.client.get(f'/auctions/{self.auction_1.id}/')
        self.assertEqual(resp_room.status_code, status.HTTP_200_OK)
        content_room = resp_room.content.decode()
        self.assertNotIn('01712345678', content_room, 'Winner phone leaked in auction room view!')
        self.assertNotIn('House 42, Road 11, Banani, Dhaka', content_room, 'Shipping address leaked in auction room view!')
        self.assertNotIn('Banani, Dhaka', content_room, 'Address substring leaked in auction room view!')

        # 2. Assert seller dashboard before settlement does NOT leak winner's phone or address
        self.client.force_login(self.seller_standard)
        resp_dash = self.client.get('/seller/dashboard/')
        self.assertEqual(resp_dash.status_code, status.HTTP_200_OK)
        content_dash = resp_dash.content.decode()
        self.assertNotIn('01712345678', content_dash, 'Winner phone leaked in seller dashboard before unlock!')
        self.assertNotIn('Banani, Dhaka', content_dash, 'Winner address leaked in seller dashboard before unlock!')

        # 3. Attempt to unlock Auction 1 with intruder credentials -> HTTP 403 Forbidden
        self.client.force_authenticate(user=self.intruder)
        resp_intruder = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')
        self.assertEqual(
            resp_intruder.status_code,
            status.HTTP_403_FORBIDDEN,
            f'Expected 403 Forbidden for intruder, got {resp_intruder.status_code}',
        )
        self.assertIn('Only the seller of this product can unlock', resp_intruder.data.get('error', ''))

        # 4. Attempt to unlock Auction 3 (status LIVE) as owner -> HTTP 400 Bad Request
        self.client.force_authenticate(user=self.seller_standard)
        resp_live = self.client.post(f'/api/auctions/{self.auction_3.id}/unlock-buyer/')
        self.assertEqual(
            resp_live.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 Bad Request for LIVE auction, got {resp_live.status_code}',
        )
        self.assertIn('Auction is still in progress', resp_live.data.get('error', ''))

    def test_scenario_b_pay_as_you_sell_standard_fee(self):
        """
        Scenario B: Path B — Pay-As-You-Sell (Standard 5% Fee).
        - Authenticate as seller_standard and unlock Auction 1.
        - Assert HTTP 200 OK with unmasked buyer details.
        - Assert DB Transaction values (final_amount=10000, platform_fee=500, covered=False, unlocked=True, status='COMPLETED').
        - Assert Auction 1 status transitioned to COMPLETED.
        - Test Idempotency: second call returns 200 OK without creating duplicate transaction or double fee.
        """
        self.client.force_authenticate(user=self.seller_standard)
        resp = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')

        # Assert response status and payload
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertEqual(data['buyer_name'], 'Rahim Uddin')
        self.assertEqual(data['buyer_phone'], '01712345678')
        self.assertIn('Banani, Dhaka', data['shipping_address'])
        self.assertEqual(Decimal(str(data['final_amount'])), Decimal('10000.00'))
        self.assertEqual(Decimal(str(data['platform_fee'])), Decimal('500.00'))
        self.assertFalse(data['covered_by_subscription'])

        # Query DB Transaction
        txn = Transaction.objects.get(auction=self.auction_1)
        self.assertEqual(txn.final_amount, Decimal('10000.00'))
        self.assertEqual(txn.platform_fee, Decimal('500.00'))
        self.assertFalse(txn.covered_by_subscription)
        self.assertTrue(txn.is_unlocked)
        self.assertEqual(txn.payment_status, Transaction.PaymentStatus.COMPLETED)
        self.assertEqual(txn.seller, self.seller_standard)
        self.assertEqual(txn.buyer, self.buyer_winner)

        # Query DB Auction 1 status
        self.auction_1.refresh_from_db()
        self.assertEqual(self.auction_1.status, Auction.Status.COMPLETED)

        # Test Idempotency: Call unlock endpoint a second time
        resp_second = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')
        self.assertEqual(resp_second.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_second.data['buyer_name'], 'Rahim Uddin')
        self.assertEqual(resp_second.data['buyer_phone'], '01712345678')
        self.assertIn('Banani, Dhaka', resp_second.data['shipping_address'])

        # Verify no duplicate transactions created
        txn_count = Transaction.objects.filter(auction=self.auction_1).count()
        self.assertEqual(txn_count, 1, f'Expected exactly 1 transaction, found {txn_count}')

    def test_scenario_c_premium_gmv_subscriber_allowance(self):
        """
        Scenario C: Path A — Premium GMV Subscriber (Allowance Consumption).
        - Authenticate as seller_premium and unlock Auction 2.
        - Assert HTTP 200 OK with unmasked buyer details.
        - Query DB Transaction: final_amount=25000.00, platform_fee=0.00, covered=True, is_unlocked=True.
        - Query DB SellerProfile: used_gmv=25000.00, remaining_gmv=175000.00.
        """
        self.client.force_authenticate(user=self.seller_premium)
        resp = self.client.post(f'/api/auctions/{self.auction_2.id}/unlock-buyer/')

        # Assert response status and payload
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertEqual(data['buyer_name'], 'Rahim Uddin')
        self.assertEqual(data['buyer_phone'], '01712345678')
        self.assertIn('Banani, Dhaka', data['shipping_address'])
        self.assertEqual(Decimal(str(data['final_amount'])), Decimal('25000.00'))
        self.assertEqual(Decimal(str(data['platform_fee'])), Decimal('0.00'))
        self.assertTrue(data['covered_by_subscription'])

        # Query DB Transaction
        txn = Transaction.objects.get(auction=self.auction_2)
        self.assertEqual(txn.final_amount, Decimal('25000.00'))
        self.assertEqual(txn.platform_fee, Decimal('0.00'))
        self.assertTrue(txn.covered_by_subscription)
        self.assertTrue(txn.is_unlocked)
        self.assertEqual(txn.payment_status, Transaction.PaymentStatus.COMPLETED)

        # Query DB SellerProfile
        self.profile_premium.refresh_from_db()
        self.assertEqual(self.profile_premium.used_gmv, Decimal('25000.00'))
        self.assertEqual(self.profile_premium.remaining_gmv, Decimal('175000.00'))

    def test_scenario_d_dashboard_view_response_integrity(self):
        """
        Scenario D: Dashboard View Response Integrity.
        - Unlock Auction 1 and Auction 2 first.
        - GET /seller/dashboard/ as seller_premium:
          * Assert HTTP 200 OK.
          * Assert context / HTML contains GMV percentage calculation (12.5% of ৳200,000 used).
          * Assert Auction 2 appears under Completed tab with unmasked contact info.
        - GET /buyer/dashboard/ as buyer_winner:
          * Assert HTTP 200 OK.
          * Assert both Won Auctions appear in the list.
        """
        # Unlock Auction 1 (Standard)
        self.client.force_authenticate(user=self.seller_standard)
        resp1 = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Unlock Auction 2 (Premium)
        self.client.force_authenticate(user=self.seller_premium)
        resp2 = self.client.post(f'/api/auctions/{self.auction_2.id}/unlock-buyer/')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

        # ── 1. Seller Dashboard (seller_premium) ───────────────────
        self.client.force_login(self.seller_premium)
        resp_seller = self.client.get('/seller/dashboard/')
        self.assertEqual(resp_seller.status_code, status.HTTP_200_OK)

        # Check GMV calculation in context and HTML
        ctx = resp_seller.context
        self.assertEqual(ctx['gmv_percentage'], 12.5, 'GMV usage percentage must be 12.5%')
        content_seller = resp_seller.content.decode()
        self.assertIn('12.5%', content_seller, '12.5% GMV usage percentage not found in HTML')

        # Check Completed Auctions tab
        completed_auctions = ctx['completed_auctions']
        self.assertEqual(len(completed_auctions), 1)
        self.assertEqual(completed_auctions[0].id, self.auction_2.id)

        # Check unmasked buyer info in completed section
        self.assertIn('Rahim Uddin', content_seller)
        self.assertIn('01712345678', content_seller)
        self.assertIn('Banani, Dhaka', content_seller)
        self.assertIn('Premium — ৳0 fee', content_seller)

        # ── 2. Buyer Dashboard (buyer_winner) ──────────────────────
        self.client.force_login(self.buyer_winner)
        resp_buyer = self.client.get('/buyer/dashboard/')
        self.assertEqual(resp_buyer.status_code, status.HTTP_200_OK)

        # Assert both won auctions appear in won_auctions list
        won_auctions = resp_buyer.context['won_auctions']
        won_auction_ids = {a.id for a in won_auctions}
        self.assertIn(self.auction_1.id, won_auction_ids, 'Auction 1 missing from buyer won auctions!')
        self.assertIn(self.auction_2.id, won_auction_ids, 'Auction 2 missing from buyer won auctions!')
        self.assertEqual(len(won_auctions), 2)

        # Assert product titles appear in rendered HTML
        content_buyer = resp_buyer.content.decode()
        self.assertIn(self.product_1.title, content_buyer)
        self.assertIn(self.product_2.title, content_buyer)

    def test_e2e_full_lifecycle_and_summary_report(self):
        """
        Full End-to-End lifecycle test executing all scenarios sequentially
        and printing the comprehensive QA & Automation Test Summary Table.
        """
        results = []

        print("\n" + "=" * 80)
        print("  BIDKORI PHASE 4 MONETIZATION & DASHBOARDS E2E INTEGRATION SUITE")
        print("=" * 80)

        # ── Test Scenario A: Security, Permissions & Data Masking ──
        try:
            # 1. Check data masking before unlock
            self.client.force_authenticate(user=self.intruder)
            room_resp = self.client.get(f'/auctions/{self.auction_1.id}/')
            self.assertEqual(room_resp.status_code, status.HTTP_200_OK)
            room_html = room_resp.content.decode()
            self.assertNotIn('01712345678', room_html)
            self.assertNotIn('Banani, Dhaka', room_html)

            self.client.force_login(self.seller_standard)
            dash_resp = self.client.get('/seller/dashboard/')
            self.assertEqual(dash_resp.status_code, status.HTTP_200_OK)
            dash_html = dash_resp.content.decode()
            self.assertNotIn('01712345678', dash_html)
            self.assertNotIn('Banani, Dhaka', dash_html)

            # 2. Intruder 403 Forbidden
            self.client.force_authenticate(user=self.intruder)
            resp_403 = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')
            self.assertEqual(resp_403.status_code, status.HTTP_403_FORBIDDEN)

            # 3. LIVE auction 400 Bad Request
            self.client.force_authenticate(user=self.seller_standard)
            resp_400 = self.client.post(f'/api/auctions/{self.auction_3.id}/unlock-buyer/')
            self.assertEqual(resp_400.status_code, status.HTTP_400_BAD_REQUEST)

            results.append(("Scenario A: Security, Permissions & Data Masking (Rule 4)", "PASS", "Masked before unlock, 403 for intruder, 400 for LIVE"))
        except Exception as e:
            results.append(("Scenario A: Security, Permissions & Data Masking (Rule 4)", "FAIL", str(e)))
            raise

        # ── Test Scenario B: Path B — Pay-As-You-Sell ───────────────
        try:
            self.client.force_authenticate(user=self.seller_standard)
            resp_b = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')
            self.assertEqual(resp_b.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_b.data['buyer_name'], 'Rahim Uddin')
            self.assertEqual(resp_b.data['buyer_phone'], '01712345678')
            self.assertIn('Banani, Dhaka', resp_b.data['shipping_address'])

            txn_1 = Transaction.objects.get(auction=self.auction_1)
            self.assertEqual(txn_1.final_amount, Decimal('10000.00'))
            self.assertEqual(txn_1.platform_fee, Decimal('500.00'))
            self.assertFalse(txn_1.covered_by_subscription)
            self.assertTrue(txn_1.is_unlocked)
            self.assertEqual(txn_1.payment_status, Transaction.PaymentStatus.COMPLETED)

            self.auction_1.refresh_from_db()
            self.assertEqual(self.auction_1.status, Auction.Status.COMPLETED)

            # Idempotency
            resp_b_idemp = self.client.post(f'/api/auctions/{self.auction_1.id}/unlock-buyer/')
            self.assertEqual(resp_b_idemp.status_code, status.HTTP_200_OK)
            self.assertEqual(Transaction.objects.filter(auction=self.auction_1).count(), 1)

            results.append(("Scenario B: Path B — Pay-As-You-Sell (Standard 5% Fee & Idempotency)", "PASS", "5% fee (৳500), COMPLETED status, idempotent duplicate calls"))
        except Exception as e:
            results.append(("Scenario B: Path B — Pay-As-You-Sell (Standard 5% Fee & Idempotency)", "FAIL", str(e)))
            raise

        # ── Test Scenario C: Path A — Premium GMV Subscriber ───────
        try:
            self.client.force_authenticate(user=self.seller_premium)
            resp_c = self.client.post(f'/api/auctions/{self.auction_2.id}/unlock-buyer/')
            self.assertEqual(resp_c.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_c.data['buyer_name'], 'Rahim Uddin')
            self.assertEqual(resp_c.data['buyer_phone'], '01712345678')
            self.assertIn('Banani, Dhaka', resp_c.data['shipping_address'])

            txn_2 = Transaction.objects.get(auction=self.auction_2)
            self.assertEqual(txn_2.final_amount, Decimal('25000.00'))
            self.assertEqual(txn_2.platform_fee, Decimal('0.00'))
            self.assertTrue(txn_2.covered_by_subscription)
            self.assertTrue(txn_2.is_unlocked)

            self.profile_premium.refresh_from_db()
            self.assertEqual(self.profile_premium.used_gmv, Decimal('25000.00'))
            self.assertEqual(self.profile_premium.remaining_gmv, Decimal('175000.00'))

            results.append(("Scenario C: Path A — Premium GMV Subscriber (Allowance)", "PASS", "৳0 fee, ৳25,000 deducted, ৳175,000 remaining GMV balance"))
        except Exception as e:
            results.append(("Scenario C: Path A — Premium GMV Subscriber (Allowance)", "FAIL", str(e)))
            raise

        # ── Test Scenario D: Dashboard View Response Integrity ────
        try:
            # Seller Dashboard
            self.client.force_login(self.seller_premium)
            resp_dash_premium = self.client.get('/seller/dashboard/')
            self.assertEqual(resp_dash_premium.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_dash_premium.context['gmv_percentage'], 12.5)
            self.assertIn('12.5%', resp_dash_premium.content.decode())
            self.assertIn('Rahim Uddin', resp_dash_premium.content.decode())
            self.assertIn('01712345678', resp_dash_premium.content.decode())

            # Buyer Dashboard
            self.client.force_login(self.buyer_winner)
            resp_buyer = self.client.get('/buyer/dashboard/')
            self.assertEqual(resp_buyer.status_code, status.HTTP_200_OK)
            won_ids = {a.id for a in resp_buyer.context['won_auctions']}
            self.assertIn(self.auction_1.id, won_ids)
            self.assertIn(self.auction_2.id, won_ids)

            results.append(("Scenario D: Dashboard View Response Integrity", "PASS", "12.5% GMV bar, completed unmasked details, 2 won auctions listed"))
        except Exception as e:
            results.append(("Scenario D: Dashboard View Response Integrity", "FAIL", str(e)))
            raise

        # ── Print Summary Table ────────────────────────────────────
        print("\n" + "-" * 88)
        print(f"{'TEST SCENARIO':<55} | {'STATUS':<8} | {'DETAILS'}")
        print("-" * 88)
        for name, outcome, details in results:
            print(f"{name:<55} | {outcome:<8} | {details}")
        print("-" * 88)
        print("  ALL PHASE 4 MONETIZATION & DASHBOARD ACCEPTANCE CRITERIA VERIFIED SUCCESSFULLY")
        print("=" * 88 + "\n")
