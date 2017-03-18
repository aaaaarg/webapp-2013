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

from flask_application.helpers import thing2opf, opf2id, opf_version

from . import db, Thing


class Metadata(db.Document):
    thing = db.ReferenceField(Thing)
    modified_at = db.DateTimeField(default=datetime.datetime.utcnow)
    opf = db.StringField()
    ol = db.DictField()
    version = db.IntField(default=1)

    def __init__(self, *args, **kwargs):
        super(Metadata, self).__init__(*args, **kwargs)
        if self.thing and not self.opf:
            self.reset_opf()

    " Builds the basic opf from the current Thing data "

    def reset_opf(self):
        self.opf = thing2opf(self.thing)
        self.save()

    def set_opf(self, raw_str, update_thing=False):
        new_version = self.is_updated(raw_str)
        if new_version:
            self.opf = raw_str
            self.modified_at = datetime.datetime.utcnow()
            self.version = new_version
            self.save()
            if update_thing:
                # @todo: now update the title and authors of the thing
                pass
            return True
        return False

    " Compares existing metadata to new metadata "

    def is_updated(self, raw_str):
        if raw_str:
            # is it the same item?
            embedded_id = opf2id(raw_str)
            if embedded_id == str(self.thing.id):
                # Is it the same version (thus the same or updated)
                v = opf_version(raw_str)
                if v > self.version:
                    # Has the metadata changed (for the better)?
                    # @todo: this one is tricky
                    return v
        return False

    def set_ol(self, data):
        if data:
            try:
                self.update(set__ol=data)
            except:
                print "Couldn't update metadata: ",data
