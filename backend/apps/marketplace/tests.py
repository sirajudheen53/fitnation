"""Tests for the marketplace app."""

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.test.utils import captured_stdout
from rest_framework.test import APITestCase

from apps.marketplace.models import (
    Cart,
    CartItem,
    Inventory,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    ProductImage,
)
from apps.marketplace import services
from apps.tenants.models import Tenant
from apps.tenants.services import provision_tenant
from apps.users.services import create_owner_user, issue_token

User = get_user_model()


def make_product(tenant: Tenant, category: ProductCategory, **kwargs) -> Product:
    """Create a product with sensible defaults for the given tenant."""
    defaults = {
        "name": "Test Product",
        "slug": "test-product",
        "description": "A test product.",
        "price": "100.00",
        "compare_price": None,
        "sku": "TEST-SKU",
        "barcode": "TEST-BARCODE",
        "brand": "TestBrand",
        "status": Product.Status.ACTIVE,
        "is_digital": False,
    }
    defaults.update(kwargs)
    return Product.objects.create(tenant=tenant, category=category, **defaults)


class ProductModelTests(TestCase):
    """Unit tests for marketplace models."""

    def setUp(self) -> None:
        """Create a tenant and category for model tests."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.category = ProductCategory.objects.create(
            tenant=self.tenant,
            name="Supplements",
            slug="supplements",
        )

    def test_product_requires_tenant(self) -> None:
        """Saving a product without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            Product.objects.create(
                name="Whey",
                category=self.category,
                slug="whey",
                price="100.00",
            )

    def test_category_requires_tenant(self) -> None:
        """Saving a category without a tenant raises ValueError."""
        with self.assertRaises(ValueError):
            ProductCategory.objects.create(name="Apparel", slug="apparel")

    def test_product_slug_unique_within_tenant(self) -> None:
        """Product slugs are unique within a tenant but reusable across tenants."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        _product(self.tenant, self.category, slug="whey", name="Whey")
        _product(other_tenant, ProductCategory.objects.create(
            tenant=other_tenant, name="Supplements", slug="supplements"), slug="whey", name="Whey")
        self.assertEqual(Product.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Product.objects.for_tenant(other_tenant).count(), 1)

    def test_product_tenant_isolation(self) -> None:
        """Products are scoped to their tenant."""
        product = _product(self.tenant, self.category, name="Dumbbells", slug="dumbbells")
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        self.assertEqual(
            Product.objects.for_tenant(self.tenant).first().id,
            product.id,
        )
        self.assertEqual(Product.objects.for_tenant(other_tenant).count(), 0)

    def test_product_defaults(self) -> None:
        """Product defaults for status and digital flag are sensible."""
        product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name="Whey",
            slug="whey",
            price="100.00",
        )
        self.assertEqual(product.status, Product.Status.DRAFT)
        self.assertFalse(product.is_digital)
        self.assertIsNone(product.compare_price)
        self.assertTrue(product.uuid)

    def test_product_is_low_stock(self) -> None:
        """is_low_stock reflects tracked inventory threshold."""
        product = _product(self.tenant, self.category, name="Whey", slug="whey")
        Inventory.objects.create(
            tenant=self.tenant,
            product=product,
            stock_quantity=2,
            low_stock_threshold=5,
        )
        self.assertTrue(product.is_low_stock)

    def test_product_not_low_stock_when_untracked(self) -> None:
        """is_low_stock is False when inventory tracking is disabled."""
        product = _product(self.tenant, self.category, name="Whey", slug="whey")
        Inventory.objects.create(
            tenant=self.tenant,
            product=product,
            stock_quantity=0,
            low_stock_threshold=5,
            track_inventory=False,
        )
        self.assertFalse(product.is_low_stock)

    def test_cart_total_and_item_total(self) -> None:
        """Cart total aggregates line item totals."""
        product = _product(self.tenant, self.category, name="Whey", slug="whey", price="100.00")
        cart = Cart.objects.create(tenant=self.tenant, user=_make_user(self.tenant))
        CartItem.objects.create(
            tenant=self.tenant, cart=cart, product=product, quantity=3, unit_price="100.00"
        )
        item = cart.items.first()
        self.assertEqual(item.total_price, 300.00)
        self.assertEqual(cart.total, 300.00)

    def test_cart_item_snapshots_unit_price(self) -> None:
        """CartItem copies the product price if no unit price is supplied."""
        product = _product(self.tenant, self.category, name="Whey", slug="whey", price="99.50")
        cart = Cart.objects.create(tenant=self.tenant, user=_make_user(self.tenant))
        item = CartItem.objects.create(
            tenant=self.tenant, cart=cart, product=product, quantity=2
        )
        self.assertEqual(float(item.unit_price), 99.50)

    def test_order_item_autocomputes_total(self) -> None:
        """OrderItem computes total_price from unit price and quantity."""
        product = _product(self.tenant, self.category, name="Whey", slug="whey", price="100.00")
        order = Order.objects.create(
            tenant=self.tenant,
            user=_make_user(self.tenant),
            total_amount="100.00",
        )
        item = OrderItem.objects.create(
            tenant=self.tenant,
            order=order,
            product=product,
            quantity=4,
            unit_price="100.00",
        )
        self.assertEqual(float(item.total_price), 400.00)

    def test_str_representations(self) -> None:
        """String representations are human-readable."""
        product = _product(self.tenant, self.category, name="Whey", slug="whey")
        self.assertEqual(str(self.category), "Supplements")
        self.assertEqual(str(product), "Whey")


def _make_user(tenant: Tenant) -> User:
    """Create a simple customer user for a tenant."""
    user = User(tenant=tenant, email="cust@local.test", first_name="C", last_name="U",
                role=User.Role.CUSTOMER)
    user.set_unusable_password()
    user.save()
    return user


def _product(tenant: Tenant, category: ProductCategory, **kwargs) -> Product:
    """Helper to create a product."""
    defaults = {
        "name": "Default Product",
        "slug": "default-product",
        "price": "100.00",
    }
    defaults.update(kwargs)
    return Product.objects.create(tenant=tenant, category=category, **defaults)


class ServiceTests(TestCase):
    """Tests for marketplace business logic services."""

    def setUp(self) -> None:
        """Create a tenant, user, category, and product."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.user = _make_user(self.tenant)
        self.category = ProductCategory.objects.create(
            tenant=self.tenant, name="Supplements", slug="supplements"
        )
        self.product = _product(self.tenant, self.category, name="Whey", slug="whey")

    def test_add_item_creates_cart_and_item(self) -> None:
        """add_item_to_cart creates a cart and line item on first add."""
        item = services.add_item_to_cart(
            tenant=self.tenant, user=self.user, product=self.product, quantity=2
        )
        cart = Cart.objects.for_tenant(self.tenant).get(user=self.user, status=Cart.Status.ACTIVE)
        self.assertEqual(item.cart.id, cart.id)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(float(item.unit_price), float(self.product.price))

    def test_add_item_increments_existing(self) -> None:
        """Adding the same product again increments the line quantity."""
        services.add_item_to_cart(self.tenant, self.user, self.product, 2)
        services.add_item_to_cart(self.tenant, self.user, self.product, 3)
        item = CartItem.objects.get(product=self.product)
        self.assertEqual(item.quantity, 5)

    def test_clear_cart_removes_items(self) -> None:
        """clear_cart empties the active cart."""
        services.add_item_to_cart(self.tenant, self.user, self.product, 2)
        services.clear_cart(tenant=self.tenant, user=self.user)
        cart = Cart.objects.for_tenant(self.tenant).get(user=self.user, status=Cart.Status.ACTIVE)
        self.assertEqual(cart.items.count(), 0)

    def test_place_order_creates_order_and_completes_cart(self) -> None:
        """place_order creates an order and marks the cart completed."""
        services.add_item_to_cart(self.tenant, self.user, self.product, 3)
        order = services.place_order(
            tenant=self.tenant,
            user=self.user,
            shipping_address="123 Main St",
            billing_address="456 Billing Ave",
        )
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(float(order.total_amount), 300.00)
        self.assertEqual(order.items.count(), 1)
        completed_cart = Cart.objects.for_tenant(self.tenant).get(user=self.user, status=Cart.Status.COMPLETED)
        self.assertEqual(completed_cart.items.count(), 0)

    def test_place_order_rejects_empty_cart(self) -> None:
        """place_order raises ValueError for an empty cart."""
        with self.assertRaises(ValueError):
            services.place_order(tenant=self.tenant, user=self.user)


class SeedCommandTests(TestCase):
    """Tests for the seed_marketplace management command."""

    def setUp(self) -> None:
        """Create a tenant for seeding."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")

    def test_seed_populates_products_and_categories(self) -> None:
        """Seeding creates sample products across categories."""
        with captured_stdout():
            call_command("seed_marketplace", tenant=self.tenant.id)
        self.assertGreaterEqual(Product.objects.for_tenant(self.tenant).count(), 5)
        categories = ProductCategory.objects.for_tenant(self.tenant)
        self.assertGreaterEqual(categories.count(), 4)
        for product in Product.objects.for_tenant(self.tenant):
            self.assertEqual(product.category.tenant_id, self.tenant.id)
            self.assertTrue(hasattr(product, "inventory"))

    def test_seed_is_idempotent(self) -> None:
        """Running the seed command twice does not duplicate products."""
        with captured_stdout():
            call_command("seed_marketplace", tenant=self.tenant.id)
        count_after_first = Product.objects.for_tenant(self.tenant).count()
        with captured_stdout():
            call_command("seed_marketplace", tenant=self.tenant.id)
        self.assertEqual(
            Product.objects.for_tenant(self.tenant).count(),
            count_after_first,
        )

    def test_seed_requires_existing_tenant(self) -> None:
        """Seeding for a missing tenant raises CommandError."""
        with self.assertRaises(CommandError):
            call_command("seed_marketplace", tenant=999999)


class MarketplaceAPIBase(APITestCase):
    """Shared setup for marketplace API tests."""

    def setUp(self) -> None:
        """Create tenant, owner, token, category, and product."""
        self.tenant = provision_tenant(name="Iron Peak", contact_email="owner@local.test")
        self.owner = create_owner_user(
            tenant=self.tenant,
            email="owner@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Owner User",
        )
        self.token = issue_token(self.owner, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.category = ProductCategory.objects.create(
            tenant=self.tenant, name="Supplements", slug="supplements"
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            name="Whey",
            slug="whey",
            price="100.00",
            sku="SKU-1",
            status=Product.Status.ACTIVE,
        )
        self.url = "/api/v1/marketplace/"


class ProductCategoryAPITests(MarketplaceAPIBase):
    """Integration tests for product category endpoints."""

    def test_list_categories(self) -> None:
        """Owner can list categories."""
        response = self.client.get(f"{self.url}categories/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Supplements")

    def test_create_category(self) -> None:
        """Owner can create a category."""
        response = self.client.post(
            f"{self.url}categories/",
            {"name": "Apparel", "slug": "apparel", "description": "Clothing."},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Apparel")
        self.assertEqual(
            ProductCategory.objects.for_tenant(self.tenant).count(), 2
        )

    def test_retrieve_category(self) -> None:
        """Owner can retrieve a category by id."""
        response = self.client.get(f"{self.url}categories/{self.category.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Supplements")

    def test_update_category(self) -> None:
        """Owner can update a category."""
        response = self.client.patch(
            f"{self.url}categories/{self.category.id}/",
            {"description": "Updated."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["description"], "Updated.")

    def test_delete_category(self) -> None:
        """Owner can delete a category."""
        response = self.client.delete(f"{self.url}categories/{self.category.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            ProductCategory.objects.for_tenant(self.tenant).count(), 0
        )


class ProductAPITests(MarketplaceAPIBase):
    """Integration tests for product endpoints."""

    def test_list_products(self) -> None:
        """Owner can list products."""
        response = self.client.get(f"{self.url}products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["category_name"], "Supplements")

    def test_create_product(self) -> None:
        """Owner can create a product with inventory."""
        response = self.client.post(
            f"{self.url}products/",
            {
                "category": self.category.id,
                "name": "Dumbbells",
                "slug": "dumbbells",
                "description": "Pair of dumbbells.",
                "price": "8999.00",
                "sku": "SKU-2",
                "status": "active",
                "inventory": {"stock_quantity": 10, "low_stock_threshold": 3},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        product = Product.objects.for_tenant(self.tenant).get(slug="dumbbells")
        self.assertEqual(product.tenant_id, self.tenant.id)
        self.assertEqual(product.inventory.stock_quantity, 10)

    def test_create_product_creates_default_inventory(self) -> None:
        """Creating a product without inventory defaults to a zero-stock row."""
        response = self.client.post(
            f"{self.url}products/",
            {
                "category": self.category.id,
                "name": "Bands",
                "slug": "bands",
                "price": "699.00",
                "sku": "SKU-3",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        product = Product.objects.for_tenant(self.tenant).get(slug="bands")
        self.assertEqual(product.inventory.stock_quantity, 0)

    def test_retrieve_product_detail(self) -> None:
        """Owner can retrieve product detail with nested data."""
        response = self.client.get(f"{self.url}products/{self.product.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["name"], "Whey")
        self.assertEqual(response.data["category_name"], "Supplements")

    def test_update_product(self) -> None:
        """Owner can update a product."""
        response = self.client.patch(
            f"{self.url}products/{self.product.id}/",
            {"price": "120.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["price"], "120.00")

    def test_delete_product(self) -> None:
        """Owner can delete a product."""
        response = self.client.delete(f"{self.url}products/{self.product.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Product.objects.for_tenant(self.tenant).count(), 0)

    def test_filter_products_by_category(self) -> None:
        """Products can be filtered by category."""
        other = ProductCategory.objects.create(
            tenant=self.tenant, name="Apparel", slug="apparel"
        )
        Product.objects.create(
            tenant=self.tenant, category=other, name="Tee", slug="tee", price="500.00"
        )
        response = self.client.get(f"{self.url}products/?category={self.category.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)


class CartAPITests(MarketplaceAPIBase):
    """Integration tests for cart endpoints."""

    def test_get_empty_cart(self) -> None:
        """GET cart returns an empty active cart."""
        response = self.client.get(f"{self.url}cart/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(Cart.objects.for_tenant(self.tenant).count(), 1)

    def test_add_item_to_cart(self) -> None:
        """POST cart adds an item."""
        response = self.client.post(
            f"{self.url}cart/",
            {"product": self.product.id, "quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["quantity"], 2)
        self.assertEqual(float(response.data["total"]), 200.00)

    def test_add_item_increments_quantity(self) -> None:
        """POST cart with an existing product increments quantity."""
        self.client.post(
            f"{self.url}cart/", {"product": self.product.id, "quantity": 2}, format="json"
        )
        response = self.client.post(
            f"{self.url}cart/", {"product": self.product.id, "quantity": 3}, format="json"
        )
        self.assertEqual(response.data["items"][0]["quantity"], 5)

    def test_add_item_requires_valid_product(self) -> None:
        """POST cart with a non-existent product returns 404."""
        response = self.client.post(
            f"{self.url}cart/", {"product": 99999, "quantity": 1}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_add_item_rejects_zero_quantity(self) -> None:
        """POST cart with quantity zero returns 400."""
        response = self.client.post(
            f"{self.url}cart/", {"product": self.product.id, "quantity": 0}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_clear_cart(self) -> None:
        """DELETE cart clears all items."""
        self.client.post(
            f"{self.url}cart/", {"product": self.product.id, "quantity": 2}, format="json"
        )
        response = self.client.delete(f"{self.url}cart/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"], [])


class CartItemAPITests(MarketplaceAPIBase):
    """Integration tests for cart item endpoints."""

    def _add_item(self) -> int:
        """Add the product to the cart and return the cart item id."""
        response = self.client.post(
            f"{self.url}cart/", {"product": self.product.id, "quantity": 2}, format="json"
        )
        return response.data["items"][0]["id"]

    def test_patch_item_quantity(self) -> None:
        """PATCH updates a cart item quantity."""
        item_id = self._add_item()
        response = self.client.patch(
            f"{self.url}cart/items/{item_id}/", {"quantity": 5}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"][0]["quantity"], 5)

    def test_patch_item_invalid_quantity(self) -> None:
        """PATCH with quantity zero returns 400."""
        item_id = self._add_item()
        response = self.client.patch(
            f"{self.url}cart/items/{item_id}/", {"quantity": 0}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_item(self) -> None:
        """DELETE removes a cart item."""
        item_id = self._add_item()
        response = self.client.delete(f"{self.url}cart/items/{item_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["items"], [])

    def test_item_scoped_to_user_cart(self) -> None:
        """A cart item from another user's cart is not accessible."""
        other = _make_user(self.tenant)
        other_cart = Cart.objects.create(tenant=self.tenant, user=other)
        other_item = CartItem.objects.create(
            tenant=self.tenant, cart=other_cart, product=self.product, quantity=1
        )
        response = self.client.delete(f"{self.url}cart/items/{other_item.id}/")
        self.assertEqual(response.status_code, 404)


class OrderAPITests(MarketplaceAPIBase):
    """Integration tests for order endpoints."""

    def _set_up_cart(self) -> None:
        """Populate the current user's active cart."""
        self.client.post(
            f"{self.url}cart/", {"product": self.product.id, "quantity": 3}, format="json"
        )

    def test_create_order_from_cart(self) -> None:
        """POST orders converts the cart into an order."""
        self._set_up_cart()
        response = self.client.post(
            f"{self.url}orders/",
            {"shipping_address": "123 Main St", "billing_address": "456 Billing Ave"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(float(response.data["total_amount"]), 300.00)
        self.assertEqual(response.data["status"], Order.Status.PENDING)
        self.assertEqual(len(response.data["items"]), 1)
        order = Order.objects.for_tenant(self.tenant).first()
        self.assertEqual(order.user_id, self.owner.id)

    def test_create_order_from_empty_cart(self) -> None:
        """POST orders with an empty cart returns 400."""
        response = self.client.post(f"{self.url}orders/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_list_orders(self) -> None:
        """Owner can list orders."""
        self._set_up_cart()
        self.client.post(f"{self.url}orders/", {}, format="json")
        response = self.client.get(f"{self.url}orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_order_items_action(self) -> None:
        """GET orders/<id>/items/ returns order line items."""
        self._set_up_cart()
        created = self.client.post(f"{self.url}orders/", {}, format="json")
        order_id = created.data["id"]
        response = self.client.get(f"{self.url}orders/{order_id}/items/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["product"], self.product.id)

    def test_orders_are_tenant_scoped(self) -> None:
        """A user cannot see another tenant's orders."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        order = Order.objects.create(
            tenant=other_tenant,
            user=_make_user(other_tenant),
            total_amount="10.00",
        )
        response = self.client.get(f"{self.url}orders/{order.id}/")
        self.assertEqual(response.status_code, 404)


class PermissionTests(MarketplaceAPIBase):
    """Integration tests for marketplace permission enforcement."""

    def test_unauthenticated_request_is_rejected(self) -> None:
        """Requests without a token are denied."""
        self.client.credentials()
        response = self.client.get(f"{self.url}products/")
        self.assertEqual(response.status_code, 401)

    def test_customer_can_view_products(self) -> None:
        """A customer role can view products and manage their own cart."""
        customer = _make_user(self.tenant)
        token = issue_token(customer, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get(f"{self.url}products/")
        self.assertEqual(response.status_code, 200)

    def test_customer_cannot_create_products(self) -> None:
        """A customer role cannot create products."""
        customer = _make_user(self.tenant)
        token = issue_token(customer, self.tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post(
            f"{self.url}products/",
            {
                "category": self.category.id,
                "name": "Sneaky",
                "slug": "sneaky",
                "price": "1.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_cross_tenant_token_is_rejected(self) -> None:
        """A token from another tenant cannot access this tenant's products."""
        other_tenant = provision_tenant(name="Other Gym", contact_email="other@local.test")
        other_owner = create_owner_user(
            tenant=other_tenant,
            email="other@local.test",
            password_hash="pbkdf2_sha256$hashed",
            contact_name="Other Owner",
        )
        other_token = issue_token(other_owner, other_tenant)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        response = self.client.get(f"{self.url}products/{self.product.id}/")
        self.assertEqual(response.status_code, 404)
