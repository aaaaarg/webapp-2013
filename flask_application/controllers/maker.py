from flask import Blueprint, render_template, flash, request, redirect, url_for, abort
from flask.ext.security import (login_required, roles_required, roles_accepted)

from flask_application.models import *

from ..permissions.thing import can_add_thing
from ..permissions.talk import can_create_thread
app.jinja_env.globals['can_add_thing'] = can_add_thing
app.jinja_env.globals['can_create_thread'] = can_create_thread


maker = Blueprint('maker', __name__, url_prefix='/maker')


@maker.route('/list')
@maker.route('/list/<letter>')
def list(letter=None):
	"""
	See a list of all things
	"""
	mi = MakerIndex()
	if letter is None:
		letter = mi.first_nonempty() # default
	makers = Maker.objects.filter(sort_by__istartswith=letter)

	return render_template('maker/list.html',
		title = 'Library (%s)' % letter,
		makers = makers,
		letters = mi.letters,
		active=letter)


@maker.route('/<id>')
def detail(id=None):
	"""
	See a maker in more detail
	"""
	maker = Maker.objects.get_or_404(id=id)
	threads = Thread.objects.filter(origin=maker)
	things = Thing.objects.filter(makers__maker=maker)
	return render_template('maker/detail.html',
		title = maker.display_name,
		maker = maker,
		things = things,
		threads = threads)


@maker.route('/<id>/things')
def things(id=None):
	"""
	See a maker in more detail
	"""
	maker = Maker.objects.get_or_404(id=id)
	things = Thing.objects.filter(makers__maker=maker)
	return render_template('maker/things.html',
		things = things)