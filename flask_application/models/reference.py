import re, datetime, urlparse

from flask.ext.security import current_user 

from . import db, CreatorMixin
from .thing import Thing
from .upload import Upload


class Annotation(CreatorMixin, db.Document):
	'''
	Base class for annotation at specific positions in an upload
	'''
	pos = db.FloatField()
	pos_end = db.FloatField()
	upload = db.ReferenceField(Upload)
	thing = db.ReferenceField(Thing)
	note = db.StringField()

	meta = {
		'allow_inheritance': True,
	}

	def __init__(self, *args, **kwargs):
		super(Annotation, self).__init__(*args, **kwargs)
		if self.upload:
			try:
				self.thing = Thing.objects.filter(files=self.upload).first()
			except Exception,e: 
				print str(e)
		if 'raw_pos' in kwargs:
			self.parse_pos(kwargs['raw_pos'])

	def _parse_pos(self, s):
		'''
		Position should be in one of the following formats:
		123 => vertical only
		123-124 => vertical range
		'''
		p = s.split('-')
		try:
			if len(p)==2:
				return float(p[0]), float(p[1])
			else:
				return float(s), None
		except:
			return None, None

	def parse_pos(self, s):
		self.pos, self.pos_end = self._parse_pos(s)


class Reference(Annotation):
	'''
	In theory, we could derive the Thing from the Upload, but that gets complicated, so storing it here 
	is essentially caching to save the work/ extra queries.
	'''
	# Messy input data - it should be parsed to fill out the *_ref fields below
	ref_url = db.StringField()
	ref_upload = db.ReferenceField(Upload)
	ref_thing = db.ReferenceField(Thing)
	ref_pos = db.FloatField()
	ref_pos_end = db.FloatField()

	def __init__(self, *args, **kwargs):
		super(Reference, self).__init__(*args, **kwargs)
		if self.ref_url:
			self._parse_url()

	def save(self, *args, **kwargs):
		super(Reference, self).save(*args, **kwargs)
		if self.ref_url:
			self._parse_url()

	def parse_ref_pos(self, s):
		self.ref_pos, self.ref_pos_end = self._parse_pos(s)

	def _parse_url(self, url=False):
		'''
		Will take an internal URL as a reference and derive the correct upload and thing
		'''
		if url:
			self.ref_url = url
		if self.ref_url:
			url_parts = urlparse.urlparse(self.ref_url)
			try:
				path = url_parts.path.split('/')
				if len(path)>1:
					self.ref_upload = Upload.objects.filter(md5=path[-1]).first()
					self.ref_thing = Thing.objects.filter(files=self.ref_upload).first()
					if url_parts.fragment:
						self.parse_ref_pos(url_parts.fragment)
					return True
			except Exception,e: 
				print str(e)
		# by default
		return False