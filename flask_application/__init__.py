import os


FLASK_APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Flask
from flask import Flask


app = Flask(__name__)

# Config
if os.getenv('DEV') == 'yes':
    app.config.from_object('flask_application.config.DevelopmentConfig')
    app.logger.info("Config: Development")
elif os.getenv('TEST') == 'yes':
    app.config.from_object('flask_application.config.TestConfig')
    app.logger.info("Config: Test")
else:
    app.config.from_object('flask_application.config.ProductionConfig')
    app.logger.info("Config: Production")

# Logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y%m%d-%H:%M%p',
)

# Email on errors
if not app.debug and not app.testing:
    import logging.handlers
    mail_handler = logging.handlers.SMTPHandler(
                        'localhost',
                        os.getenv('USER'),
                        app.config['SYS_ADMINS'],
                        '{0} error'.format(app.config['SITE_NAME'],
                        ),
                    )
    mail_handler.setFormatter(logging.Formatter('''
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
    '''.strip()))
    mail_handler.setLevel(logging.ERROR)
    app.logger.addHandler(mail_handler)
    app.logger.info("Emailing on error is ENABLED")
else:
    app.logger.info("Emailing on error is DISABLED")

# Assets
from flask.ext.assets import Environment
assets = Environment(app)
# Ensure output directory exists
assets_output_dir = os.path.join(FLASK_APP_DIR, 'static', 'gen')
if not os.path.exists(assets_output_dir):
    os.mkdir(assets_output_dir)

# Ensure uploads directory exists
assets_upload_dir = app.config['UPLOADS_DIR']
if not os.path.exists(assets_upload_dir):
    os.mkdir(assets_upload_dir)


# Email
from flask.ext.sendmail import Mail, Message
mail = Mail(app)

# Memcache
from werkzeug.contrib.cache import MemcachedCache
app.cache = MemcachedCache(app.config['MEMCACHED_SERVERS'])
def cache_fetch(key, value_function, timeout=None):
    '''Mimicking Rails.cache.fetch'''
    global app
    self = app.cache
    data = self.get(key)
    if data is None:
        data = value_function()
        self.set(key, data, timeout)
    return data
app.cache.fetch = cache_fetch

# Helpers
from flask_application.helpers import datetimeformat
app.jinja_env.filters['datetimeformat'] = datetimeformat

# Markdown
from flaskext.markdown import Markdown
Markdown(app)

# Business Logic
# http://flask.pocoo.org/docs/patterns/packages/
# http://flask.pocoo.org/docs/blueprints/
from flask_application.controllers import frontend, thing, maker, collection, queue, talk, user, upload, admin
app.register_blueprint(frontend.frontend)
app.register_blueprint(thing.thing)
app.register_blueprint(collection.collection)
app.register_blueprint(queue.queue)
app.register_blueprint(upload.upload)
app.register_blueprint(maker.maker)
app.register_blueprint(talk.talk)
app.register_blueprint(user.user)
#app.register_blueprint(admin.admin)

# Setup Flask-Security
from flask.ext.security import Security, MongoEngineUserDatastore, current_user
from flask_application.models import db, User, Role
from flask_application.security_extras import ExtendedRegisterForm

user_datastore = MongoEngineUserDatastore(db, User, Role)
app.security = Security(app, user_datastore,
         register_form=ExtendedRegisterForm)

# Flask security lets us override how the mail is sent, which is necessary to use flask-sendmail
@app.security.send_mail_task
def sendmail_with_sendmail(msg):
    msg_copy = Message(msg.subject, recipients=msg.recipients, body=msg.body, html=msg.html,
                sender=msg.sender, cc=msg.cc, bcc=msg.bcc, attachments=msg.attachments,
                reply_to=msg.reply_to)
    mail.send(msg_copy)

#from flask_application.controllers.admin import admin
#app.register_blueprint(admin)

# Info block
app.jinja_env.globals['info_block'] = app.config['INFO_BLOCK']

