from functools import partial


from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form
from flask.ext.mongoengine.wtf.fields import QuerySetSelectField
from flask.ext.security import current_user

from wtforms import TextField, BooleanField, HiddenField
from wtforms.widgets import Select, HTMLString, html_params
from wtforms.validators import Required

from ..models import Collection, SuperCollection, CollectedThing, Thing, Cache
from ..permissions.collection import *


CollectionForm = model_form(SuperCollection, base_class=Form)


class SelectWithOptgroup(Select):
    """
    Override Select field to add optgroup capabilities
    """

    def __call__(self, field, **kwargs):
        def iter_choices(choices):
            html = []
            for x in choices:
                if len(x) == 3:
                    val, label, selected = x
                    html.append(self.render_option(val, label, selected))
                elif len(x) == 2:
                    options = iter_choices(x[1])
                    html.append(self.render_group(x[0], options))
            return HTMLString(''.join(html))

        kwargs.setdefault('id', field.id)
        if self.multiple:
            kwargs['multiple'] = True
        html = ['<select %s>' % html_params(name=field.name, **kwargs)]
        html.append(iter_choices(field.iter_choices()))
        html.append('</select>')
        return HTMLString(''.join(html))

    @classmethod
    def render_group(cls, label, options, **kwargs):
        return HTMLString('<optgroup label="%s">%s</option>' % (label, HTMLString(''.join(options))))


class CollectionQuerySetSelectField(QuerySetSelectField):
    """
    Special handling for dynamic Collection select field
    """
    widget = SelectWithOptgroup()

    def __init__(self, *args, **kwargs):
        super(CollectionQuerySetSelectField, self).__init__(*args, **kwargs)
        self.queryset = {}
        self.queryset['following'] = Collection.objects.filter(
            supercollection__exists=False, followers=current_user.get_id()).order_by('title')
        self.queryset['contributing'] = Collection.objects.filter(
            supercollection__exists=False, editors=current_user.get_id()).order_by('title')
        self.queryset['created'] = Collection.objects.filter(
            supercollection__exists=False, creator=current_user.get_id()).order_by('title')

    def process_formdata(self, valuelist):
        """
        Make sure the queryset is initialized before processing the formdata or it will fail
        """
        if valuelist:
            if valuelist[0] == '__None':
                self.data = None
            else:
                if self.queryset is None:
                    self.data = None
                    return
                try:
                    # clone() because of
                    # https://github.com/MongoEngine/mongoengine/issues/56
                    obj = Collection.objects.get(id=valuelist[0])
                    self.data = obj
                except DoesNotExist:
                    self.data = None

    def build_flat_hierarchy(self):
        """
        The query set is only top level collections - the "hierarchy" is basically a query set including subcollections
        """
        # first try the cache
        cached = Cache.objects(name="collections-for-%s" %
                               current_user.get_id()).first()
        if cached:
            self.hierarchy = cached.value
            return True
        # not in cache, so we have to build it, which is expensive
        self.hierarchy = {}

        def recurse(objs, depth, group):
            for obj in objs:
                # if not obj.has_thing(self.thing):
                label = self.label_attr and getattr(
                    obj, self.label_attr) or obj
                self.hierarchy[group].append((obj, depth))
                if obj.subcollections:
                    recurse(obj.subcollections, depth + 1, group)

        for group in self.queryset:
            self.hierarchy[group] = []
            self.queryset[group].rewind()
            recurse(self.queryset[group], 0, group)

        cached = Cache(name="collections-for-%s" %
                       current_user.get_id(), value=self.hierarchy)
        cached.save()

    def iter_choices(self):
        self.build_flat_hierarchy()

        if self.allow_blank:
            yield (u'__None', self.blank_text, self.data is None)

        if self.queryset is None:
            return

        def iter_group_choices(flat_hierarchy):
            for obj, depth in flat_hierarchy:
                if can_add_thing_to_collection(obj):
                    label = self.label_attr and getattr(
                        obj, self.label_attr) or obj
                    label = "%s %s" % (
                        '-' * depth, label) if depth > 0 else label
                    if isinstance(self.data, list):
                        selected = obj in self.data
                    else:
                        selected = self._is_selected(obj)
                    yield (obj.id, label, selected)

        for group in self.hierarchy:
            yield (group, (iter_group_choices(self.hierarchy[group])))

    def set_thing(self, thing):
        self.thing = thing


class AddThingToCollectionsBase(Form):
    """
    Provides a hidden field for storing Thing ids that are to be sorted into 
    a selection of Collections
    """
    collection = CollectionQuerySetSelectField(
        u'Collections', label_attr='title', allow_blank=True)

    def __init__(self, *args, **kwargs):
        super(AddThingToCollectionsBase, self).__init__(*args, **kwargs)

    def set_thing(self, thing):
        self.thing.queryset = Thing.objects.filter(id=thing.id)
        self.collection.set_thing(thing)


AddThingToCollectionsForm = model_form(
    CollectedThing, base_class=AddThingToCollectionsBase)
