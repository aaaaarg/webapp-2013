import os,binascii

from flask import Blueprint, render_template, flash, request, redirect, url_for, abort
from flask.ext.mail import Message
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from flask.ext.security.utils import encrypt_password

from flask_application.models import *
from flask_application.forms import InviteForm, UserForm

from ..permissions.thing import can_edit_thing

user = Blueprint('user', __name__, url_prefix='/user')



@user.route('/profile')
@user.route('/profile/<int:page>')
@login_required
def profile(page=1):
	"""
	A person's own profile
	"""
	things = Thing.objects.filter(creator=current_user.get_id()).order_by('-created_at').paginate(page=page, per_page=10)
	collections = Collection.objects.filter(creator=current_user.get_id(), supercollection__exists=False)
	
	return render_template('profiles/profile.html',
		title = 'Uploads',
		things = things.items,
		pagination = things,
		collections = collections,
		public=False)


@user.route('/profile/edit', methods=['GET','POST'])
@login_required
def edit_profile():
	"""
	Edit one's own profile
	"""
	user = User.objects.get_or_404(id=current_user.get_id())
	form = UserForm(formdata=request.form, obj=user)
	if form.validate_on_submit():
		user.email = form.email.data
		user.username = form.username.data
		user.save()
		flash("Your profile has been updated!")
	return render_template('profiles/edit.html',
		title = 'Edit your account',
		form = form)


@user.route('/<id>')
@user.route('/<id>/<int:page>')
@login_required
def public_profile(id, page=1):
	"""
	Other peoples profiles
	"""
	user = User.objects.get_or_404(id=id)
	things = Thing.objects.filter(creator=id).order_by('-created_at').paginate(page=page, per_page=10)
	collections = Collection.objects.filter(creator=id, supercollection__exists=False)
	
	return render_template('profiles/profile.html',
		title = user.username,
		things = things.items,
		pagination = things,
		collections = collections,
		public=True)


@user.route('/invite', methods=['GET','POST'])
@login_required
def invite():
	"""
	Invite a new person
	"""
	form = InviteForm(request.form)
	if form.validate_on_submit():
		from flask_application import user_datastore, app, mail
		user = User.objects(id=current_user.get_id()).first()
		password = binascii.b2a_hex(os.urandom(15))
		# create an account
		user_datastore.create_user(username="x", 
			email=form.email.data, 
			password=encrypt_password(password),
			roles=['contributor'], 
			active=True,
			invited_by=user)
		user_datastore.commit()
		invitee = User.objects(email=form.email.data).first()
		# set inviter data
		user.add_invitation(invitee)
		# send an email
		msg = Message("An invitation to %s" % app.config['SITE_NAME'],
			sender=app.config['DEFAULT_MAIL_SENDER'],
			recipients=[form.email.data])
		msg.body = '''
			You have been invited to %s by %s. 
			Your can log in with the following username/ password:
			%s
			%s
			You can change this random, complicated password after you have logged in.
			''' % (app.config['SITE_NAME'], user.email, form.email.data, password)
		mail.send(msg)
		# @todo: set invited and invited by
		flash("An account has been created for %s and an email has been sent. You may want to let them know that it is coming." % form.email.data)
	return render_template('profiles/invite.html',
		register_user_form = form)



@user.route('/collections')
def collections(letter=None):
	"""
	See a list of collections the user has created or is following
	"""
	following = Collection.objects.filter(supercollection__exists=False, followers=current_user.get_id()).order_by('title')
	contributing = Collection.objects.filter(supercollection__exists=False, editors=current_user.get_id()).order_by('title')
	created = Collection.objects.filter(supercollection__exists=False, creator=current_user.get_id()).order_by('title')
	
	return render_template('collection/user_list.html',
		title = 'Collections',
		following = following,
		contributing = contributing,
		created = created)

