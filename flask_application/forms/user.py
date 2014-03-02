from wtforms import TextField, BooleanField, HiddenField
from wtforms.validators import Email
from flask.ext.wtf import Form
from flask.ext.mongoengine.wtf import model_form
from flask.ext.security.forms import RegisterForm, Required, TextField, _datastore, get_message, ValidationError

from ..models import User


def unique_username(form, field):
		if _datastore.find_user(email=field.data) is not None:
			msg = "%s may already have an account" % field.data
			raise ValidationError(msg)

def same_or_unique_username(form, field):
		if not form.existing_email.data==field.data:
			if _datastore.find_user(email=field.data) is not None:
				msg = "Sorry, you cannot change your email address to %s" % field.data
				raise ValidationError(msg)

class BaseUserForm(Form):
	existing_email = HiddenField(u'Existing Email', default=None)

	def __init__(self, *args, **kwargs):
		super(BaseUserForm, self).__init__(*args, **kwargs)
		if self.existing_email.data is None:
			 self.existing_email.data = self.email.data


InviteForm = model_form(User, base_class=Form, only=['email'], field_args={
		'email' : {
        'validators' : [Required(), Email(), unique_username]
    }})

UserForm = model_form(User, base_class=BaseUserForm, only=['email', 'username'], field_args={
		'email' : {
        'validators' : [Required(), Email(), same_or_unique_username]
    },
    'username' : {
        'validators' : [Required()]
    }})