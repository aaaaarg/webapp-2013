import datetime

from sunburnt import SolrInterface

from flask_application import app

from flask.ext.security import current_user 
from flask.ext.mongoengine import MongoEngine

# Create db, which is used across all models
db = MongoEngine(app)

# Create solr interface
solr = SolrInterface(app.config['SOLR_SERVER_URL'])

# Import user models here, before mixins
from .user import User, Role
# Import rest of models here
from .base import CreatorMixin, FollowersMixin, EditorsMixin, SolrMixin
from .user import User, Role
from .thing import Thing
from .collection import Collection, SuperCollection, CollectedThing, CollectionIndex
from .maker import Maker, Name, MakerIndex
from .upload import Upload, TextUpload, UploadManager
from .talk import Thread, Comment
from .queue import Queue, QueuedThing
from .cache import Cache
