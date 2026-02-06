from celery import Celery
from flask import current_app
from flask_mail import Message
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import os

celery = Celery(__name__)

@celery.task
def send_confirmation_email(email, order_id):
    with current_app.app_context():
        from app import mail
        msg = Message('Order Confirmation', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your order #{order_id} has been placed successfully.'
        mail.send(msg)

@celery.task
def generate_invoice(order_id, customer_email, product_name, quantity, total_price):
    filename = f'invoice_{order_id}.pdf'
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    c = canvas.Canvas(filepath, pagesize=letter)
    c.drawString(100, 750, f'Invoice for Order #{order_id}')
    c.drawString(100, 730, f'Customer: {customer_email}')
    c.drawString(100, 710, f'Product: {product_name}')
    c.drawString(100, 690, f'Quantity: {quantity}')
    c.drawString(100, 670, f'Total: ${total_price}')
    c.save()
    return filepath

@celery.task
def reduce_stock(product_id, quantity):
    with current_app.app_context():
        from models import Product, db
        product = db.session.get(Product, product_id)
        if product:
            product.stock -= quantity
            db.session.commit()

@celery.task
def create_thumbnail(image_path, thumbnail_path):
    with Image.open(image_path) as img:
        img.thumbnail((200, 200))
        img.save(thumbnail_path)
