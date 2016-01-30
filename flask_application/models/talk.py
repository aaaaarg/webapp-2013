import re
import datetime

from bson import ObjectId

from flask import url_for
from flask.ext.security import current_user

from flask_application.helpers import merge_dicts
from . import *


class Comment(CreatorMixin, db.EmbeddedDocument):
    """
    Each individual comment
    """
    _id = db.ObjectIdField(default=ObjectId())
    text = db.StringField()


class Thread(SolrMixin, CreatorMixin, FollowersMixin, db.Document):
    """
    Thread model - represents a discussion thread. Includes comments within.
    """
    meta = {
        'ordering': ['-last_comment']
    }

    title = db.StringField(max_length=255, default="General discussion")
    comments = db.ListField(db.EmbeddedDocumentField(Comment))
    origin = db.GenericReferenceField()
    last_comment = db.DateTimeField(
        default=datetime.datetime.now, required=True)
    last_comment_by = db.ReferenceField(User)
    last_comment_text = db.StringField(default="")
    priority = db.IntField(default=0)

    @property
    def type(self):
        return 'thread'

    # Creates a new comment and adds it to Talk thread
    def add_comment(self, text, user=None, created_at=None):
        comment = Comment(text=text, created_at=created_at)
        comment.set_creator(user)
        self.update(add_to_set__comments=comment)
        self.last_comment = comment.created_at
        self.last_comment_by = comment.creator
        self.last_comment_text = text
        self.save()
        self.tell_followers('New comment: %s' % self.title, '''
			A new comment has been posted to <a href="%s">%s</a>:
			
			%s
			- %s
			''' % (url_for('talk.thread', id=self.id, _external=True), self.title, text, comment.creator.username))

    # Sets the origin
    def set_origin(self, type, id):
        if type == 'Maker':
            self.origin = Maker.objects(id=id).first()
        elif type == 'Collection':
            self.origin = Collection.objects(id=id).first()
        elif type == 'Thing':
            self.origin = Thing.objects(id=id).first()

    # Title of origin
    def origin_title(self):
        if not self.origin:
            return ""
        if isinstance(self.origin, Maker):
            return self.origin.display_name
        if isinstance(self.origin, Collection):
            return self.origin.title
        if isinstance(self.origin, Thing):
            return "%s (%s)" % (self.origin.title, self.origin.format_makers_string())

    def build_solr(self):
        searchable = ' '.join([c.text for c in self.comments])
        searchable = "%s %s" % (self.origin_title, searchable)
        return {
            '_id': self.id,
            'content_type': 'thread',
            'title': self.title,
            'searchable_text': searchable
        }

    def populate_comment_creators(self):
        """
        Fetches all comment creators (i.e. users) for this thread
        in a single query, and populates the Comment documents with them.

        Calling this method is useful when you're iterating
        through all comments and their creators, and you want to avoid
        the N+1 performance problem (making a database hit each iteration).
        """
        user_ids = set(map(lambda comment: str(
            comment._data['creator'].id), self.comments))
        users = User.objects.filter(id__in=user_ids)
        user_ids_to_users = reduce(lambda reduced, user: merge_dicts(
            reduced, {str(user.id): user}), users, dict())
        for comment in self.comments:
            comment.creator = user_ids_to_users[
                str(comment._data['creator'].id)]
