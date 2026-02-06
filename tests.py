import os
os.environ['CELERY_BROKER_URL'] = 'memory://'
os.environ['CELERY_RESULT_BACKEND'] = 'cache'

import unittest
import uuid
from unittest.mock import patch
from flask import Flask
from flask_testing import TestCase
from app import create_app
from models import db, User, Product, Order
from flask_login import login_user
from tasks import celery
celery.conf.update(broker_url='memory://', result_backend='cache')

class TestMarketplaceApp(TestCase):

    def create_app(self):
        self.db_uri = f'sqlite:///test_{uuid.uuid4().hex}.db'
        os.environ['DATABASE_URL'] = self.db_uri
        os.environ['CELERY_BROKER_URL'] = 'memory://'
        os.environ['CELERY_RESULT_BACKEND'] = 'cache'
        app = create_app(test=True)
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = self.db_uri
        app.config['task_always_eager'] = True  # Run tasks synchronously in tests
        celery.conf.update(app.config)  # Update celery config with test settings
        return app

    def setUp(self):
        db.drop_all()
        db.create_all()
        # Create test user
        self.test_user = User(username='testuser', email='test@example.com', password='hashedpass', role='customer')
        db.session.add(self.test_user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        if os.path.exists(self.db_uri[10:]):  # Remove 'sqlite:///'
            os.remove(self.db_uri[10:])

    def test_user_registration(self):
        """Test user registration functionality"""
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123',
            'role': 'customer'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Registration successful', response.data)

    def test_product_creation(self):
        """Test product creation by seller"""
        # Create seller user
        seller = User(username='seller', email='seller@example.com', password='hashedpass', role='seller')
        db.session.add(seller)
        db.session.commit()

        with self.client:
            login_user(seller)
            response = self.client.post('/add_product', data={
                'name': 'Test Product',
                'description': 'Test Description',
                'price': '10.99',
                'stock': '5'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Product added successfully', response.data)

    @patch('views.orders.send_confirmation_email.delay')
    def test_order_placement(self, mock_send_email):
        """Test order placement"""
        # Create seller and product
        seller = User(username='seller', email='seller@example.com', password='hashedpass', role='seller')
        db.session.add(seller)
        db.session.flush()
        db.session.commit()
        product = Product(name='Test Product', description='Test', price=10.99, stock=10, seller_id=seller.id)
        db.session.add(product)
        db.session.commit()

        with self.client:
            login_user(self.test_user)
            response = self.client.post(f'/place_order/{product.id}', data={
                'quantity': '2'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Order placed successfully', response.data)
            mock_send_email.assert_called_once()

    def test_role_based_access(self):
        """Test role-based access control"""
        # Test customer trying to add product
        with self.client:
            login_user(self.test_user)
            response = self.client.get('/add_product')
            self.assertEqual(response.status_code, 302)  # Should redirect

    def test_product_search(self):
        """Test product search functionality"""
        # Create products
        seller = User(username='seller', email='seller@example.com', password='hashedpass', role='seller')
        db.session.add(seller)
        db.session.flush()
        db.session.commit()
        product1 = Product(name='Laptop', description='Gaming laptop', price=1000.0, stock=5, seller_id=seller.id)
        product2 = Product(name='Phone', description='Smartphone', price=500.0, stock=10, seller_id=seller.id)
        db.session.add_all([product1, product2])
        db.session.commit()

        with self.client:
            response = self.client.get('/products?search=laptop')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Laptop', response.data)
            self.assertNotIn(b'Phone', response.data)

    def test_order_status_update(self):
        """Test order status update by seller"""
        # Create seller and customer
        seller = User(username='seller', email='seller@example.com', password='hashedpass', role='seller')
        customer = User(username='customer', email='customer@example.com', password='hashedpass', role='customer')
        db.session.add_all([seller, customer])
        db.session.commit()
        # Create product and order
        product = Product(name='Test Product', description='Test', price=10.99, stock=10, seller_id=seller.id)
        db.session.add(product)
        db.session.flush()
        order = Order(product_id=product.id, user_id=customer.id, quantity=2, total_price=21.98, status='pending')
        db.session.add(order)
        db.session.commit()

        with self.client:
            login_user(seller)
            response = self.client.post(f'/update_order_status/{order.id}', data={'status': 'shipped'}, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Order status updated successfully', response.data)

    def test_invalid_product_data(self):
        """Test adding product with invalid data"""
        seller = User(username='seller', email='seller@example.com', password='hashedpass', role='seller')
        db.session.add(seller)
        db.session.commit()

        with self.client:
            login_user(seller)
            response = self.client.post('/add_product', data={
                'name': '',  # Invalid: empty name
                'price': 'invalid_price',  # Invalid: non-numeric
                'stock': '5'
            }, follow_redirects=True)
            self.assertIn(b'Name, price, and stock are required', response.data)

    def test_add_to_cart(self):
        """Test adding product to cart"""
        # Create seller and product
        seller = User(username='seller', email='seller@example.com', password='hashedpass', role='seller')
        db.session.add(seller)
        db.session.flush()
        db.session.commit()
        product = Product(name='Test Product', description='Test', price=10.99, stock=10, seller_id=seller.id)
        db.session.add(product)
        db.session.commit()

        with self.client:
            login_user(self.test_user)
            response = self.client.post(f'/add_to_cart/{product.id}', data={
                'quantity': '2'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Product added to cart', response.data)

if __name__ == '__main__':
    unittest.main()
