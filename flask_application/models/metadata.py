"""
Stores OPF metadata. It is probably redundant with the data that is stored in 
the Thing collection and very likely to get out of sync (without a lot of effort),
but the purpose is to (a) generate a simple .opf metadata file that can be imported
into Calibre and (b) handle syncs/updates from Calibre plugins.

Ideally, the updated Calibre metadata would then be used to update the Thing and 
Makers associated with the metadata - thus allowing people to use Calibre's 
powerful tools for metadata editing.

Given this anticipated use, the data structure is - for now - a raw text representation
of the .opf file (which is XML) along with a reference to the Thing id and also a date 
of last update (to help with syncing and conflict resolution).
"""
import datetime

from flask_application.helpers import thing2opf, opf2id, opf_date

from . import db, Thing

class Metadata(db.Document):
	thing = db.ReferenceField(Thing)
	modified_at = db.DateTimeField(default=datetime.datetime.utcnow)
	opf = db.StringField()

	def __init__(self, *args, **kwargs):
		super(Metadata, self).__init__(*args, **kwargs)
		if self.thing and not self.opf:
			self.reset_opf()

	" Builds the basic opf from the current Thing data "
	def reset_opf(self):
		self.opf = thing2opf(self.thing)
		self.save()

	def set_opf(self, raw_str, update_thing=False):
		if raw_str:
			embedded_id = opf2id(raw_str)
			modified = opf_date(raw_str)
			if embedded_id==str(self.thing.id) and self.modified_at < modified:
				self.opf = raw_str
				self.modified_at = modified
				self.save()
				if update_thing:
					# @todo: now update the title and authors of the thing
					pass
