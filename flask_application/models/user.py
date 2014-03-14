from flask.ext.security import UserMixin, RoleMixin

from . import db

# Define models
class Role(db.Document, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)
    
    def __unicode__(self):
        return self.name    

class User(db.Document, UserMixin):
    meta = {
        'indexes': ['email']
    }
    email = db.StringField(max_length=255)
    username = db.StringField(max_length=255)
    password = db.StringField(max_length=255)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField(Role), default=[])
    # these are both user types
    invited_by = db.GenericReferenceField()
    invited = db.ListField(db.GenericReferenceField())

    def eq(self, user):
    	if not self.is_anonymous() and self.get_id()==user.id:
    		return True
    	return False

    def add_invitation(self, user):
        self.update(add_to_set__invited=user)

    def set_inviter(self, user):
        self.update(set__invited_by=user)
