from bson import ObjectId

from flask import abort
from flask.ext.security import current_user 

from . import db, CreatorMixin, EditorsMixin, FollowersMixin, SolrMixin
from .user import User
from .thing import Thing
from .cache import Cache


TYPES = (('private', 'Private: It should not appear in the list of collections. Only you (or people you invite) can add and remove items.'),
    ('semi-public', 'Public: It should be visible in the list of collections. But only invited collaborators can change what is in it.'),
    ('public', 'Shared: The list is visible and anyone at all can add to this list - only collaborators can remove things.'))


class CollectedThing(CreatorMixin, db.EmbeddedDocument):
    """
    Represents a thing in a collection or subcollection
    """
    _id = db.ObjectIdField()
    thing = db.ReferenceField(Thing)
    note = db.StringField()

    def __init__(self, *args, **kwargs):
        super(CollectedThing, self).__init__(*args, **kwargs)
        if not self._id:
            self._id = ObjectId()


class Collection(SolrMixin, CreatorMixin, EditorsMixin, FollowersMixin, db.DynamicDocument):
    """
    Base class for collections and subcollections
    """
    meta = {
        'allow_inheritance': True,
        'ordering': ['title']
    }
    # fields
    title = db.StringField(max_length=255)
    short_description = db.StringField(max_length=512)
    description = db.StringField()
    things = db.ListField(db.EmbeddedDocumentField(CollectedThing))
    accessibility = db.StringField(max_length=16, choices=TYPES)

    def has_thing(self, thing):
        if thing is None:
            return False
        for collected_thing in self.things:
            if collected_thing.thing is not None and collected_thing.thing.id == thing.id:
                return True
        return False


    def get_collected_thing(self, thing):
        if thing is None:
            return False
        for collected_thing in self.things:
            if collected_thing.thing is not None and collected_thing.thing.id == thing.id:
                return collected_thing
        return False


    def add_thing(self, collected_thing=None, thing=None, note=''):
        if thing and not collected_thing:
            collected_thing = CollectedThing(thing=thing, note=note)
        if not self.has_thing(collected_thing.thing):
            self.update(add_to_set__things=collected_thing)

    def remove_thing(self, thing, return_collected_thing=False):
        if return_collected_thing:
            ct = self.get_collected_thing(thing)
            self.update(pull__things__thing=thing)
            return ct
        else:
            self.update(pull__things__thing=thing)

    def get_note_for_thing(self, thing):
        for collected_thing in self.things:
            if collected_thing.thing is not None and collected_thing.thing.id == thing.id:
                return collected_thing.note
        return ''

    def added_thing(self, thing, user=None):
        """
        Did a user add the thing to this collection?
        """
        for collected_thing in self.things:
            if collected_thing.thing is not None and collected_thing.thing.id == thing.id:
                return collected_thing.is_creator(user)
        return False

    def build_solr(self):
        if self.accessibility=='private':
            return {}
        searchable = ' '.join(["%s %s" % (ct.thing.title, ct.thing.format_makers_string()) for ct in self.things])
        return {
            '_id' : self.id,
            'content_type' : 'collection',
            'title': self.title,
            'short_description': self.short_description,
            'description': self.description,
            'searchable_text': searchable,
            'things' : [ct.thing.id for ct in self.things]
        }    

class SuperCollection(Collection):
    """
    Collection model
    """
    subcollections = db.ListField(db.ReferenceField(Collection))
    supercollection = db.ReferenceField(Collection)
    weight = db.IntField()

    def add_subcollection(self, subcollection):
        self.update(add_to_set__subcollections=subcollection)

    # Gets all parents, children, and sibling collections
    def family(self, include_self=True):
        root = self
        while root.supercollection:
            root = root.supercollection

        def gather_children(c):
            f = [] if not include_self and c.id==self.id else [c]
            for sc in c.subcollections:
                f.extend(gather_children(sc))
            return f
        return gather_children(root)


    def set_subcollection_weights(self, weights):
        for sc in self.subcollections:
            if str(sc.id) in weights:
                sc.update(set__weight=weights[str(sc.id)])
            sc.set_subcollection_weights(weights)

    def has_editor(self, user, include_supercollections=True):
        """
        Determines whether the user is in the list of editors
        """
        # collection, user, include_supercollections
        def check(c, u, s):
            if Collection.has_editor(c, u):
                return True
            elif s and c.supercollection:
                return check(c.supercollection, u, s)
            return False

        return check(self, user, include_supercollections)

    def has_follower(self, user, include_supercollections=True):
        """
        Determines whether the user is in the list of followers
        """
        # collection, user, include_supercollections
        def check(c, u, s):
            if Collection.has_follower(c, u):
                return True
            elif s and c.supercollection:
                return check(c.supercollection, u, s)
            return False

        return check(self, user, include_supercollections)


class CollectionIndex():
    """
    Represents the index of collection titles
    """
    _cache_name = 'collection_index_letters'
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
            letters[c] = len(Collection.objects.filter(title__istartswith=c))
        return letters

    def first_nonempty(self):
        for l, c in self.letters.iteritems():
            if c>0:
                return l
