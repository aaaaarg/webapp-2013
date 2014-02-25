import re

from flask.ext.security import current_user 

from . import db


class Cache(db.Document):
	name = db.StringField(max_length=64)
	value = db.DictField()