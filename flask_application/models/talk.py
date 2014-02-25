import re, datetime

from bson import ObjectId

from flask.ext.security import current_user 

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
	last_comment = db.DateTimeField(default=datetime.datetime.now, required=True)
	last_comment_by = db.ReferenceField(User)
	last_comment_text = db.StringField(default="")

	# Creates a new comment and adds it to Talk thread
	def add_comment(self, text, user=None, created_at=None):
		comment = Comment(text=text, created_at=created_at)
		comment.set_creator(user)
		self.update(add_to_set__comments=comment)
		self.last_comment = comment.created_at
		self.last_comment_by = comment.creator
		self.last_comment_text = text
		self.save()

	# Sets the origin
	def set_origin(self, type, id):
		if type=='Maker':
			self.origin = Maker.objects(id=id).first()
		elif type=='Collection':
			self.origin = Collection.objects(id=id).first()
		elif type=='Thing':
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
			'_id' : self.id,
			'content_type' : 'thread',
			'title': self.title,
			'searchable_text': searchable 
		}  
