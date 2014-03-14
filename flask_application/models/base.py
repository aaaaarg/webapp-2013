import datetime, sys, traceback

from unidecode import unidecode
from sunburnt.schema import SolrError

from flask_application import app, mail
from flask.ext.mail import Message
from flask.ext.security import current_user 

from . import db, solr, User

# Gets a user object from the current user
def current_user_obj():
    try:
        return User.objects(id=current_user.get_id()).first()
    except:
        return None

# Mixes in creation details for documents (user and date)
class CreatorMixin(object):
    """
    Base document class for providing functionality to all models:
    creator, creation date
    """
    #meta = {'allow_inheritance': True}
    # creator refers to the user who submitted this thing (maker is the author/ creator of the thing itself)
    created_at = db.DateTimeField(default=datetime.datetime.now, required=True)
    creator = db.ReferenceField(User, default=current_user_obj)

    def set_creator(self, user=None):
        if user is None:
            try:
                user = current_user_obj()
            except:
                user = None
        self.creator = user

    def is_creator(self, user=None):
        if user is None:
            user = current_user
        try:
            if self.creator.id == current_user.id:
                return True
        except:
            return False
        return False


# Mixes in follower fields
class FollowersMixin(object):
    """
    List of users designated as follower
    """
    followers = db.ListField(db.ReferenceField(User))
    num_followers = db.IntField()

    def add_follower(self, user):
        self.update(add_to_set__followers=user)
        self.update(set__num_followers=len(self.followers))

    def remove_follower(self, user):
        self.update(pull__followers=user)
        self.update(set__num_followers=len(self.followers))

    def has_follower(self, user):
        for u in self.followers:
            if user.eq(u):
                return True
        return False

    # current user is following?
    def is_follower(self):
        return self.has_follower(current_user_obj())

    # broadcasts a message to all followers
    def tell_followers(self, subject, content):
        msg = Message(subject,
            sender=app.config['DEFAULT_MAIL_SENDER'],
            recipients=[app.config['DEFAULT_MAIL_REPLY_TO']])
        # add followers
        if 'SEND_NOTIFICATIONS' in app.config and app.config['SEND_NOTIFICATIONS']:
            for u in self.followers:
                if u.active:
                    msg.bcc.append(u.email)
        # add body and then send
        msg.html = content
        try:
            mail.send(msg)
        except:
            print 'Failed to tell followers:',content

# Mixes in editor fields
class EditorsMixin(object):
    """
    List of users designated as editor
    """
    editors = db.ListField(db.ReferenceField(User))

    def add_editor(self, user):
        self.update(add_to_set__editors=user)

    def remove_editor(self, user):
        self.update(pull__editors=user)

    def has_editor(self, user):
        for u in self.editors:
            if user.eq(u):
                return True
        return False

    # current user is following?
    def is_editor(self):
        return self.has_editor(current_user_obj())


# Mixes in Solr indexing functionality
class SolrMixin(object):

    solr_dict = {}

    def add_to_solr(self, commit=True):
        d = self.build_solr()
        if not d:
            # if the dict is empty, then it shouldn't be indexed
            return
        for k in d:
            if isinstance(d[k], basestring):
                d[k] = unidecode(d[k])
        try:
            solr.add(d)
            if commit:
                solr.commit()
        except SolrError as e:
            print "SolrError: ", e
        except:
            print "Unexpected error:", sys.exc_info()[0]
            print traceback.print_tb(sys.exc_info()[2])
            print d

    def delete_from_solr(self):
        solr.delete(self)
        solr.commit()

    def build_solr(self):
        super(SolrMixin, self).build_solr(*args, **kwargs)

    def save(self, *args, **kwargs):
        super(SolrMixin, self).save(*args, **kwargs)
        self.add_to_solr()

    def delete(self, *args, **kwargs):
        self.delete_from_solr()
        super(SolrMixin, self).delete(*args, **kwargs)

    #def update(self, *args, **kwargs):
    #    super(SolrMixin, self).update(*args, **kwargs)
    #    self.add_to_solr()
