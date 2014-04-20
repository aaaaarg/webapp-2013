from flask import Blueprint, render_template, get_template_attribute, flash, request, redirect, url_for, abort, jsonify
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from mongoengine import Q
from flask.ext.mongoengine.wtf import model_form

from flask_application import app
from flask_application.models import *
from flask_application.forms import CollectionForm, AddThingToCollectionsForm

# Set up perms for use in views and templates
from ..permissions.collection import *
from ..permissions.talk import can_create_thread
app.jinja_env.globals['can_create_thread'] = can_create_thread
app.jinja_env.globals['can_add_collection'] = can_add_collection
app.jinja_env.globals['can_edit_collection'] = can_edit_collection
app.jinja_env.globals['can_follow_collection'] = can_follow_collection
app.jinja_env.globals['can_unfollow_collection'] = can_unfollow_collection
app.jinja_env.globals['can_remove_thing_from_collection'] = can_remove_thing_from_collection
app.jinja_env.globals['can_add_thing_to_collection'] = can_add_thing_to_collection


# Set up blueprint
collection = Blueprint('collection', __name__, url_prefix='/collection')

# -- jinja filters

@collection.app_template_filter()
def format_collection_link(collection, separator=" - "):
	"""
	Returns a link to the collection, but includes ancestors if they exist
	"""
	link = render_template('collection/link.html',
		collection = collection)
	if 'supercollection' in collection:
		link = "%s%s%s" % (format_collection_link(collection.supercollection, separator), separator, link)
	return link


# -- views below

@collection.route('/list')
@collection.route('/list/<letter>')
def list(letter=None):
	"""
	See a list of collections
	"""
	ci = CollectionIndex()
	if letter is None:
		letter = ci.first_nonempty() # default
	collections = Collection.objects.filter(title__istartswith=letter, accessibility__ne='private', supercollection__exists=False )

	return render_template('collection/list.html',
		title = 'Collections (%s)' % letter,
		collections = collections,
		letters = ci.letters,
		active = letter)


@collection.route('/<id>')
def detail(id):
	"""
	See a collection in more detail
	"""
	collection = Collection.objects.get_or_404(id=id)
	threads = Thread.objects.filter(origin=collection)
	return render_template('collection/detail.html',
		collection = collection,
		threads = threads)


@collection.route('/<id>/edit', methods= ['GET', 'POST'])
def edit(id):
	"""
	Edit a thing
	"""
	model = Collection.objects.get_or_404(id=id)
	if not can_edit_collection(model):
		abort(403)
	form = CollectionForm(formdata=request.form, obj=model, exclude=['creator'])
	if form.validate_on_submit():
		model.title = form.title.data
		model.short_description = form.short_description.data
		model.description = form.description.data
		model.save() 
		flash("Collection updated")
		return redirect(url_for("collection.detail", id=model.id))
	return render_template('collection/edit.html',
		title = 'Edit',
		form = form)


@collection.route('/<id>/rearrange', methods= ['GET', 'POST'])
def rearrange(id):
	"""
	Rearranges subcollection
	"""
	c = Collection.objects.get_or_404(id=id)
	#if not can_edit_collection(c):
	#	abort(403)
	if not len(c.subcollections)>0:
		flash("You can't re-order the subcollections - there are no subcollections, yet!")
		return detail(id)
	if request.form:
		weights = {}
		weight = 1
		for key in request.form.keys():
			for value in request.form.getlist(key):
				if key=='o[]':
					weights[value.encode('utf-8').strip()] = weight
					weight = weight + 1
		c.set_subcollection_weights(weights)
		return jsonify({'message':'hello'})
	else:
		return render_template('collection/rearrange.html',
			title = 'Re-order subcollections of %s' % c.title,
			collection = c
	  )


@collection.route('/<id>/subcollection/add', methods= ['GET', 'POST'])
def add_subcollection(id):
	"""
	Add a new subcollection
	"""
	c = Collection.objects.get_or_404(id=id)
	form = CollectionForm(exclude=['creator'], accessibility=c.accessibility)
	if form.validate_on_submit():
		sc = SuperCollection()
		form.populate_obj(sc)
		sc.supercollection = c
		sc.save()
		c.add_subcollection(sc)
		flash("Subcollection created")
		return redirect(url_for("collection.detail", id=c.id))
	return render_template('collection/edit.html',
		title = 'Start a Subcollection in %s' % c.title,
		form=form,
		collection = c
  )


@collection.route('/add/thing/<thing_id>', methods= ['POST'])
def add_thing(thing_id):
	"""
	Adds a thing to a collection. The collection and a note are submitted via form.
	"""
	thing = Thing.objects.get_or_404(id=thing_id)
	cf = AddThingToCollectionsForm(formdata=request.form)
	cf.set_thing(thing)
	if cf.validate_on_submit():
		collection = cf.collection.data
		if not collection.has_thing(thing):
			collection.add_thing(thing=thing, note=cf.note.data)
		return jsonify({
			'result':'success', 
			'message':'Added to <a href="%s">%s</a>!' % (url_for('collection.detail', id=collection.id), collection.title), 
			'collection':get_template_attribute('collection/macros.html', 'show_collections_list_item')(collection, thing)})
	return jsonify({'result':'error', 'message':'Sorry, there was a problem'})


@collection.route('/move/<thing_id>/from/<collection_id_from>/to/<collection_id_to>', methods= ['GET', 'POST'])
def move_thing(collection_id_from, collection_id_to, thing_id):
	"""
	Is both a removing from a collection and adding to another collection
	"""
	cf = Collection.objects.get_or_404(id=collection_id_from)
	ct = Collection.objects.get_or_404(id=collection_id_to)
	t = Thing.objects.get_or_404(id=thing_id)
	if not can_add_thing_to_collection(ct, t) or not can_remove_thing_from_collection(cf, t):
		abort(403)
	collected_thing = cf.remove_thing(t,return_collected_thing=True)
	ct.add_thing(collected_thing)
	flash("%s moved from %s to %s" % (t.title, cf.title, ct.title))
	return redirect(url_for("collection.detail", id=cf.id))


@collection.route('/<collection_id>/remove/<thing_id>', methods= ['GET', 'POST'])
def remove(collection_id, thing_id):
	"""
	Remove a thing from a collection
	"""
	c = Collection.objects.get_or_404(id=collection_id)
	t = Thing.objects.get_or_404(id=thing_id)
	#if not can_remove_thing_from_collection(c, t):
	#	abort(403)
	c.remove_thing(t)
	if not c.has_thing(t):
		flash("%s removed from Collection" % t.title)
	return redirect(url_for("collection.detail", id=c.id))


@collection.route('/add', methods= ['GET', 'POST'])
@roles_accepted('admin', 'editor', 'contributor')
def add():
	"""
	Add a new collection
	"""
	form = CollectionForm(exclude=['creator'])
	if form.validate_on_submit():
		model = SuperCollection()
		form.populate_obj(model)
		model.save() 
		flash("Collection created")
		return redirect(url_for("collection.list"))
	return render_template('collection/edit.html',
		title = 'Start a Collection',
		form=form
  )


@collection.route('/for/thing/<thing_id>', methods= ['GET'])
def list_for_thing(thing_id):
	"""
	A list of collections and optional form
	"""
	thing = Thing.objects.get_or_404(id=thing_id)
	collections = Collection.objects.filter(things__thing=thing)
	# Add this thing to one or more collections
	if can_add_thing_to_collections():
		cf = AddThingToCollectionsForm(formdata=request.form)
		cf.set_thing(thing)
		if cf.validate_on_submit():
			ct = CollectedThing()
			cf.populate_obj(ct)
			cf.collection.data.add_thing(ct)
		form_template = get_template_attribute('collection/macros.html', 'add_to_collection_form')(cf)
		return get_template_attribute('collection/macros.html', 'show_collections_list')(collections, thing, form_template)
	else:
		return get_template_attribute('collection/macros.html', 'show_collections_list')(collections, thing)


@collection.route('/<id>/followers')
def list_followers(id):
	"""
	Removes current user as follower
	Returns JSON
	"""
	model = Collection.objects.get_or_404(id=id)
	editors = model.editors
	followers = model.followers
	for editor in editors:
		if editor in followers:
			followers.remove(editor)
	return get_template_attribute('collection/macros.html', 'list_followers')(followers, editors, model)


@collection.route('/<id>/editor/<user_id>/add', methods= ['GET', 'POST'])
def add_editor(id, user_id):
	"""
	Add an editor to a collection
	"""
	c = Collection.objects.get_or_404(id=id)
	u = User.objects.get_or_404(id=user_id)
	if not can_edit_collection(c):
		abort(403)
	c.add_editor(u)
	flash("%s added as editor to %s" % (u.username, c.title))
	return redirect(url_for("collection.detail", id=id))


@collection.route('/<id>/editor/<user_id>/remove', methods= ['GET', 'POST'])
def remove_editor(id, user_id):
	"""
	Remove an editor from a collection
	"""
	c = Collection.objects.get_or_404(id=id)
	u = User.objects.get_or_404(id=user_id)
	if not can_edit_collection(c):
		abort(403)
	c.remove_editor(u)
	flash("%s removed as editor from %s" % (u.username, c.title))
	return redirect(url_for("collection.detail", id=id))

