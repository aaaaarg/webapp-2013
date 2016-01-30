import re
import datetime

from flask.ext.security import current_user

from . import db

# Could also be more days


def one_day(days=1):
    return datetime.datetime.now() + datetime.timedelta(days=days)


class Cache(db.Document):
    name = db.StringField(max_length=64)
    expires = db.DateTimeField(default=one_day, required=True)
    value = db.DictField()

    def __init__(self, *args, **kwargs):
        super(Cache, self).__init__(*args, **kwargs)
        if not self.expires or self.expires < datetime.datetime.now():
            self.delete()

    def set_expiration(self, days):
        self.expires = one_day(days=days)

    def expire(self):
        self.delete()
