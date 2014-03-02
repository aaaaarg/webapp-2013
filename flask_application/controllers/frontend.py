#!/usr/bin/env python

import datetime

from flask import Blueprint, request, redirect, url_for, render_template, get_template_attribute, abort, jsonify
from flask_application import app
from flask.ext.security import login_required, current_user

from ..models import *

frontend = Blueprint('frontend', __name__)

@frontend.route('/')
def index():
	return redirect(url_for("thing.list_nonrequests"))
	return render_template(
		'index.html',
		config=app.config,
		now=datetime.datetime.now,
	)


@frontend.route('/follow/<type>/<id>')
def follow(type, id):
	"""
	Adds current user to followers
	Returns JSON
	"""
	if type=='collection':
		model = Collection.objects.get_or_404(id=id)
	elif type=='queue':
		model = Queue.objects.get_or_404(id=id)
	elif type=='maker':
		model = Maker.objects.get_or_404(id=id)
	elif type=='thread':
		model = Thread.objects.get_or_404(id=id)
	else:
		abort(404)

	user = User.objects(id=current_user.id).first()	
	model.add_follower(user)
	return jsonify({
		'result': 'success',
		'message': get_template_attribute('frontend/macros.html', 'unfollow')(model)
	})


@frontend.route('/unfollow/<type>/<id>')
def unfollow(type, id):
	"""
	Removes current user as follower
	Returns JSON
	"""
	if type=='collection':
		model = Collection.objects.get_or_404(id=id)
	elif type=='queue':
		model = Queue.objects.get_or_404(id=id)
	elif type=='maker':
		model = Maker.objects.get_or_404(id=id)
	elif type=='thread':
		model = Thread.objects.get_or_404(id=id)
	else:
		abort(404)

	user = User.objects(id=current_user.id).first()
	model.remove_follower(user)
	return jsonify({
		'result': 'success',
		'message': get_template_attribute('frontend/macros.html', 'follow')(model)
	})


@frontend.route('/search')
@frontend.route('/search/<type>')
def search(type=False):
	is_ajax = request.args.get('ajax', None)
	query = request.args.get('query', "")
	page = int(request.args.get('page', "1"))
	if not type:
		return render_template(
			'frontend/search.html',
			query = query,
			title = 'Search for'
		)
	if is_ajax and query=="":
		return 'I am not searching for anything'
	num = 10
	start = (page-1)*num
	if type=='things':
		results = solr.query(content_type="thing", text=query).boost_relevancy(3, title=query).paginate(start=start, rows=num).execute()
		content = get_template_attribute('frontend/macros.html', 'search_results')(results, 'thing.detail')			
	elif type=='makers':
		results = solr.query(content_type="maker", text=query).boost_relevancy(3, title=query).paginate(start=start, rows=num).execute()
		content = get_template_attribute('frontend/macros.html', 'search_results')(results, 'maker.detail')
	elif type=='discussions':
		results = solr.query(content_type="thread", text=query).boost_relevancy(2, title=query).paginate(start=start, rows=num).execute()
		content = get_template_attribute('frontend/macros.html', 'search_results')(results, 'talk.thread')
	elif type=='collections':
		results = solr.query(content_type="collection", text=query).boost_relevancy(3, title=query).paginate(start=start, rows=num).execute()
		content = get_template_attribute('frontend/macros.html', 'search_results')(results, 'collection.detail')
	if is_ajax:
		return content
	else: 
		return render_template(
		'frontend/search_results.html',
		query = query,
		title = 'Search for',
		content = content,
		page_next = page + 1,
		type = type
	)