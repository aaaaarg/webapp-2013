import datetime

from flask_application import app
from flask_application.elastic import ES

from flask.ext.security import current_user 
from flask.ext.mongoengine import MongoEngine

# Create db, which is used across all models
db = MongoEngine(app)

# Set up Elastic Search
elastic = ES(app)


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
from .reference import Reference, Annotation
from .cache import Cache
from .metadata import Metadata
