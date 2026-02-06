import logging
from flask import Flask, redirect, url_for, render_template
from app.config import Config
from app.tasks import celery
from app.extensions import db, login_manager, mail

def create_app(test=False):
    app = Flask(__name__, template_folder='app/templates', static_folder='app/static')
    app.config.from_object(Config)

    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    if not test:
        celery.conf.update(app.config)

    from app.views.auth import auth_bp
    from app.views.products import products_bp
    from app.views.orders import orders_bp
    from app.views.cart import cart_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(cart_bp)

    with app.app_context():
        db.create_all()

    @app.route('/')
    def home():
        return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return db.session.get(User, int(user_id))

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
