import datetime
from bson import ObjectId

from flask import abort
from flask.ext.security import current_user 

from . import db, CreatorMixin, EditorsMixin, FollowersMixin, SolrMixin
from .user import User
from .thing import Thing
from .cache import Cache


TYPES = (('private', 'Draft: Only you and site administrators can see the notes.'),
    ('public', 'Published: Anyone can see the notes.'))


class QueuedThing(CreatorMixin, db.Document):
    """
    Represents a thing in a queue
    """
    thing = db.ReferenceField(Thing)
    weight = db.IntField()
    short_description = db.StringField(max_length=255)
    date_scheduled = db.DateTimeField()
    date_completed = db.DateTimeField()
    subtitle = db.StringField(max_length=255)
    description = db.StringField()
    accessibility = db.StringField(max_length=16, choices=TYPES)    

class Queue(CreatorMixin, EditorsMixin, FollowersMixin, db.Document):
    """
    Queue class
    """
    # fields
    title = db.StringField(max_length=255)
    short_description = db.StringField(max_length=512)
    description = db.StringField()
    things = db.ListField(db.ReferenceField(QueuedThing))

    last_updated = db.DateTimeField()

    def add_thing(self, thing, short_description=''):
        queued_thing = QueuedThing(thing=thing, short_description=short_description, weight=len(self.things)+1)
        queued_thing.save()
        self.update(add_to_set__things=queued_thing)
        self.last_updated = datetime.datetime.now

    def remove_thing(self, qt):
        # warning: id is the QueuedThing id, not the Thing id
        self.update(pull__things=qt)

    def finish_thing(self, qt):
        # warning: id is the QueuedThing id, not the Thing id
        qt.update(set__date_completed=datetime.datetime.now)

    def unfinish_thing(self, qt):
        # warning: id is the QueuedThing id, not the Thing id
        qt.update(set__date_completed=None)

    def set_weights(self, weights):
        for qt in self.things:
            if str(qt.id) in weights:
                qt.update(set__weight=weights[str(qt.id)])

