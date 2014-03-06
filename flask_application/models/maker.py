import re

from flask.ext.security import current_user 

from nameparser import HumanName

from . import db, CreatorMixin, FollowersMixin, SolrMixin
from .user import User
from .cache import Cache


class Name(db.EmbeddedDocument):
    """
    Structure for holding a name
    """
    title = db.StringField(max_length=16)
    first = db.StringField(max_length=64)
    middle = db.StringField(max_length=64)
    last = db.StringField(max_length=96)
    suffix = db.StringField(max_length=16)

    def parse(self, raw):
        """
        A raw string representing a name is parsed into Name structure
        """
        parsed = HumanName(raw)
        self.title = parsed.title.encode('utf-8').strip()
        self.first = parsed.first.encode('utf-8').strip()
        self.middle = parsed.middle.encode('utf-8').strip()
        self.last = parsed.last.encode('utf-8').strip()
        self.suffix = parsed.suffix.encode('utf-8').strip()

    def formal_name(self):
        n = "%s %s %s %s %s" % (self.title, self.first, self.middle, self.last, self.suffix)
        return re.sub(' +', ' ' , n)

    def full_name(self):
        n = "%s %s %s %s" % (self.first, self.middle, self.last, self.suffix)
        return re.sub(' +', ' ' , n)

    def sort_name(self):
        n = "%s, %s, %s, %s, %s" % (self.last, self.first, self.middle, self.suffix, self.title)
        return re.sub(' +', ' ' , n)


class Maker(SolrMixin, CreatorMixin, FollowersMixin, db.Document):
    """
    Maker model
    """
    meta = {
        'ordering': ['sort_by']
    }
    name = db.EmbeddedDocumentField(Name)
    disambiguation = db.StringField(max_length=256)
    display_name = db.StringField(max_length=256)
    sort_by = db.StringField(max_length=256)

    def format_name(self, role=None):
        if role is None or role=="":
            return self.display_name
        else:
            return "%s (%s)" % (self.display_name, role)

    def init_with_name(self, name, display_name=None):
        self.name = name
        if display_name is None:
            self.display_name = name.full_name()
        self.sort_by = name.sort_name()


    def build_solr(self):
        from .thing import Thing
        things = Thing.objects.filter(makers__maker=self)
        # If the maker is not associated with any things, then don't index it 
        if things.count()==0:
            return {}
        searchable = ' '.join(["%s %s" % (t.title, t.short_description) for t in things])
        return {
            '_id' : self.id,
            'content_type' : 'maker',
            'title': self.display_name,
            'searchable_text': searchable,
            'things' : [t.id for t in things]
        }    

class MakerIndex():
    """
    Represents the index of names
    """
    _cache_name = 'maker_index_letters'
    letters = {}

    def __init__(self):
        cached = Cache.objects(name=self._cache_name).first()
        if cached:
            self.letters = cached.value
        else:
            self.letters = self.compute_letters()
            Cache(name=self._cache_name, value=self.letters).save() 

    def rebuild_cache(self):
        letters = self.compute_letters()
        Cache.objects(name=_cache_name).update(name=self._cache_name, value=letters)

    def compute_letters(self):
        from string import ascii_lowercase
        letters = {}
        for c in ascii_lowercase:
            letters[c] = len(Maker.objects.filter(sort_by__istartswith=c))
        return letters

    def first_nonempty(self):
        for l, c in self.letters.iteritems():
            if c>0:
                return l