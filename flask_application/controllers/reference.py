#!/usr/bin/env python

import datetime, os, rfc3987, re
from math import floor
from PIL import Image

from flask import Blueprint, request, redirect, flash, url_for, render_template, send_file, abort, jsonify
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from flask_application import app
from flask_application.helpers import parse_pos
from flask_application.forms import ReferenceForm

from ..models import *
from ..permissions.reference import *

reference = Blueprint('reference', __name__)

@reference.route('/annotation/<id>/edit', methods= ['GET', 'POST'])
def edit(id):
	"""
	Edit a reference
	"""
	r = Reference.objects.get_or_404(id=id)
	if not can_edit_reference(r):
		abort(403)
	form = ReferenceForm(formdata=request.form, obj=r, exclude=['creator','thing','upload','ref_pos','ref_pos_end','ref_thing','ref_upload'])
	if form.validate_on_submit():
		form.populate_obj(r)
		r.save() 
		flash("Reference updated")
		return redirect("%s#%s" % (url_for("reference.figleaf", md5=r.upload.md5), r.pos))
	return render_template('reference/edit.html',
		title = 'Edit',
		form = form,
		reference = r)


@reference.route('/reference/form', methods=['GET'])
@reference.route('/reference/form/<md5>', methods=['GET', 'POST'])
@reference.route('/reference/form/<md5>/<pos>', methods=['GET', 'POST'])
def add_reference(md5=None, pos=None):
	"""
	Create a new reference
	"""
	m = request.args.get('md5', None) if md5 is None else md5
	u = Upload.objects.filter(md5=m).first()
	if not u:
		abort(404)	
	p = request.args.get('pos', None) if pos is None else pos
	t, b = parse_pos(p)
	# make the form
	form = ReferenceForm(formdata=request.form, pos=t, exclude=['creator','thing','upload','ref_pos','ref_pos_end','ref_thing','ref_upload'])
	
	if form.validate_on_submit():
		
		reference = Reference()
		form.populate_obj(reference)
		reference.tags = form.tags_proxy.data
		reference.upload = u
		reference.save()
		return jsonify({'message':'Success! The reference has been created.'})
	else:
		img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (t-.03, t+.03, 500))) 
		return render_template('reference/add_reference.html',
			form=form,
			img=img,
			md5=m,
			pos=t
	  )


@reference.route('/clip/form', methods=['GET'])
@reference.route('/clip/form/<md5>', methods=['GET', 'POST'])
@reference.route('/clip/form/<md5>/<pos>', methods=['GET', 'POST'])
def add_clip(md5=None, pos=None):
	"""
	Create a new clip
	"""
	m = request.args.get('md5', None) if md5 is None else md5
	u = Upload.objects.filter(md5=m).first()
	if not u:
		abort(404)
	p = request.args.get('pos', None) if pos is None else pos
	t, b = parse_pos(p)
	# make the form
	form = ReferenceForm(formdata=request.form, pos=t, pos_end=b, exclude=['creator','thing','upload','ref_pos','ref_pos_end','ref_thing','ref_upload'])
	del form.ref_url

	if form.validate_on_submit():
		reference = Reference()
		form.populate_obj(reference)
		reference.tags = form.tags_proxy.data
		reference.upload = u
		reference.save()
		return jsonify({'message':'Success! The clip has been created.'})
	else:
		pdf = None
		if b-t>1:
			pdf = url_for("reference.preview", filename='compile/%s.pdf/%s-%s/pdf.pdf' % (m, int(t), int(b)), _external=True)
		img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (t, b, 500)), _external=True) 
		highlight = url_for("reference.figleaf", md5=m, _anchor="%s-%s"%(t,b), _external=True)
		return render_template('reference/add_clip.html',
			form=form,
			img=img,
			pdf=pdf,
			md5=m,
			highlight_url = highlight
	  )


@reference.route('/<id>/delete', methods= ['GET','POST'])
def delete(id):
	"""
	Delete a reference
	"""
	model = Reference.objects.get_or_404(id=id)
	if not can_edit_reference(model):
		abort(403)
	md5 = model.upload.md5
	pos = model.pos
	model.delete()
	flash("Reference deleted")
	return redirect("%s#%s" % (url_for("reference.figleaf", md5=md5), pos))


@reference.route('/pages/<path:filename>')
def preview(filename):
	abort(404)


@reference.route('/read/<string:md5>.<format>')
def pdf2html(md5, format):
	# only text and html conversion allowed
	if not format=='txt' and not format=='html':
		abort(404)
	u = Upload.objects.filter(md5=md5).first()
	if not u:
		abort(404)
	content = u.extract_pdf_text(format)
	if not content:
		return "Sorry, this didn't work out."
	else:
		return "<pre>%s</pre>" % content	


@reference.route('/ref/<string:md5>/search-inside')
def search_inside(md5):
	""" Conduct a search inside the text """
	search_results = {}
	query = request.args.get('query', '')
	if not query=='':
		subqueries = query.split(',')
		q_idx = 0
		for q in subqueries:
			if q_idx==3:
				continue
			new_query = "'%s'" % q.strip()
			results = solr.query(searchable_text=new_query).filter(content_type="page").filter(md5_s=md5).field_limit("_id", score=True).sort_by("-score").execute()
			max_score = 0
			min_score = 100
			search_results[q_idx] = {}
			for result in results:
				print result
				if '_id' in result:
					# id[0] is the upload id, id[1] is upload page
					id = str(result['_id']).split('_')
					if len(id)==2:
						search_results[q_idx][id[1]] = result['score']
						max_score = result['score'] if result['score'] > max_score else max_score
						min_score = result['score'] if result['score'] < min_score else min_score
			min_score = min_score - 0.1
			search_results[q_idx].update((x, (y-min_score)/(max_score-min_score)) for x, y in search_results[q_idx].items())
			q_idx+=1
	return jsonify(search_results)


@reference.route('/ref/<string:md5>')
@reference.route('/ref/<string:md5>/<user_id>')
def figleaf(md5, user_id=None):
	"""
	The filename here is the structured filename
	"""
	u = Upload.objects.filter(md5=md5).first()
	if not u:
		abort(404)
	thing = Thing.objects.filter(files=u).first()

	preview = u.preview()
	preview_url = url_for('reference.preview', filename=preview) if preview else False
	#preview_url = preview_url.replace('/pages', 'http://127.0.0.1:8484')
	if not preview_url:
		abort(404)

	# load annotations
	#annotations = Reference.objects.filter(upload=u, ref_url__exists=True)
	annotations = Reference.objects.filter(upload=u).order_by('ref_pos')
	# create a list of referenced things
	references = {}
	# the annotations/ reference that the user can edit
	editable = []

	for a in annotations:
		if can_edit_reference(a):
			editable.append(a)
		if a.ref_thing and a.ref_pos and a.ref_url:
			if not a.ref_thing in references:
				references[a.ref_thing] = { 'md5':a.ref_upload.md5, 'pages':[] }
			references[a.ref_thing]['pages'].append(a.ref_pos)

	# for back references
	back_annotations = Reference.objects.filter(ref_upload=u).order_by('pos')
	back_references = {}
	for a in back_annotations:
		if a.thing and a.pos:
			if not a.thing in back_references:
				back_references[a.thing] = { 'md5':a.upload.md5, 'pages':[] }
			back_references[a.thing]['pages'].append(a.pos)

	# if we pass a user id then we try and load highlights & notes created by the user
	if user_id:
		notes = Reference.objects.filter(upload=u, creator=user_id)
	else:
		notes = Reference.objects.filter(upload=u, creator=current_user.get_id())

	# if there is a query specified, do it
	is_searchable = False
	search_results = {}
	query = request.args.get('query', '')
	if not query=='':
		subqueries = query.split(',')
		q_idx = 0
		for q in subqueries:
			if q_idx==3:
				continue
			new_query = "'%s'" % q.strip()
			results = solr.query(searchable_text=new_query).filter(content_type="page").filter(md5_s=md5).field_limit("_id", score=True).sort_by("-score").execute()
			max_score = 0
			min_score = 100
			search_results[q_idx] = {}
			for result in results:
				is_searchable = True
				if '_id' in result:
					# id[0] is the upload id, id[1] is upload page
					id = str(result['_id']).split('_')
					if len(id)==2:
						search_results[q_idx][id[1]] = result['score']
						max_score = result['score'] if result['score'] > max_score else max_score
						min_score = result['score'] if result['score'] < min_score else min_score
			min_score = min_score - 0.1
			search_results[q_idx].update((x, (y-min_score)/(max_score-min_score)) for x, y in search_results[q_idx].items())
			q_idx+=1

	# check if this is searchable
	if not is_searchable:
		results = solr.query().filter(content_type="page").filter(md5_s=md5).execute()
		if results:
			is_searchable = True

	return render_template('reference/figleaf.html',
		preview = preview_url,
		upload=u,
		thing = thing,
		annotations = annotations,
		references = references,
		back_annotations = back_annotations,
		back_references = back_references,
		notes = notes,
		editable = editable,
		search_results = search_results,
		searchable=is_searchable
		)


@reference.route('/ref/<string:md5>/add/<float:pos>')
@login_required
def create_reference(md5, pos):
	"""
	Adds a reference notation to an upload
	"""
	url = request.args.get('url', '')
	if not rfc3987.match(url, rule='URI'):
		return "Sorry, that's not a valid URL:\n" % url
	u = Upload.objects.filter(md5=md5).first()
	if not u:
		abort(404)
	# Create the reference
	r = Reference(upload=u, ref_url=url, pos=pos)
	r.save()
	
	return url

@reference.route('/ann/<string:md5>/add/<string:pos>')
@login_required
def create_annotation(md5, pos):
	"""
	Adds a reference notation to an upload
	"""
	note = request.args.get('note', '')
	u = Upload.objects.filter(md5=md5).first()
	if not u:
		abort(404)
	# Create the reference
	r = Reference(upload=u, note=note, raw_pos=pos)
	# try and extract a url
	urls = re.findall(r'(https?://\S+)', note)
	for url in urls:
		if r._parse_url(url):
			break

	r.save()
	return ''


@reference.route('/clips/about/<string:tag>')
@reference.route('/clips/about/<string:tag>/<user_id>')
def tag_clips(tag, user_id=None):
	if user_id is not None:
		annotations = Reference.objects.filter(creator=user_id, tags=tag).order_by('-created_at')
	else:
		annotations = Reference.objects.filter(tags=tag).order_by('-created_at')
	clips = []

	for a in annotations:
		if a.pos_end:
			u = a.upload
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor='%s-%s' % (a.pos, a.pos_end))
			y1, y2 = (a.pos, a.pos_end) if a.pos_end-a.pos<1 else (int(a.pos), int(a.pos))
			if a.pos_end-a.pos>1:
				a.note = '%s (%s pages)' % (a.note, int(a.pos_end)-int(a.pos)+1)
			img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (y1, y2, 500)))
			clips.append((link,img,a.note,a.tags))

	return render_template('reference/clips.html',
		title = "Clips for %s" % tag,
		thing = thing,
		clips = clips
	)


@reference.route('/clips')
@reference.route('/clips/for/<user_id>')
def user_clips(user_id=None):
	if user_id is None:
		user_id = current_user.get_id()

	annotations = Reference.objects.filter(creator=user_id).order_by('-created_at')
	clips = []

	for a in annotations:
		if a.pos_end:
			u = a.upload
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor='%s-%s' % (a.pos, a.pos_end))
			y1, y2 = (a.pos, a.pos_end) if a.pos_end-a.pos<1 else (int(a.pos), int(a.pos))
			if a.pos_end-a.pos>1:
				a.note = '%s (%s pages)' % (a.note, int(a.pos_end)-int(a.pos)+1)
			img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (y1, y2, 500)))
			clips.append((link,img,a.note,a.tags))

	return render_template('reference/clips.html',
		title = "clips",
		thing = thing,
		clips = clips
	)

@reference.route('/clips/recent')
@reference.route('/clips/recent/<int:page>')
def recent_clips(page=1):
	annotations = Reference.objects(pos_end__gt=0).order_by('-created_at').paginate(page=page, per_page=20)
	clips = []

	for a in annotations.items:
		if a.pos_end:
			u = a.upload
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor='%s-%s' % (a.pos, a.pos_end))
			y1, y2 = (a.pos, a.pos_end) if a.pos_end-a.pos<1 else (int(a.pos), int(a.pos))
			if a.pos_end-a.pos>1:
				a.note = '%s (%s pages)' % (a.note, int(a.pos_end)-int(a.pos)+1)
			img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (y1, y2, 500)))
			clips.append((link,img,a.note,a.tags))

	return render_template('reference/clips.html',
		title = "clips",
		thing = thing,
		clips = clips
	)

@reference.route('/clips/from/<string:md5>')
@reference.route('/clips/from/<string:md5>/<user_id>')
def clips(md5, user_id=None):
	"""
	A page made of clips/ highlights of the text
	"""
	u = Upload.objects.filter(md5=md5).first()
	thing = Thing.objects.filter(files=u).first()
	if not u:
		abort(404)
	# load annotations
	if user_id:
		annotations = Reference.objects.filter(upload=u, creator=user_id).order_by('pos')
	else:
		annotations = Reference.objects.filter(upload=u).order_by('pos')
	clips = []

	for a in annotations:
		if a.pos_end:
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor='%s-%s' % (a.pos, a.pos_end))
			y1, y2 = (a.pos, a.pos_end) if a.pos_end-a.pos<1 else (int(a.pos), int(a.pos))
			if a.pos_end-a.pos>1:
				a.note = '%s (%s pages)' % (a.note, int(a.pos_end)-int(a.pos)+1)
			img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (y1, y2, 500)))
			clips.append((link,img,a.note,a.tags))

	return render_template('reference/clips.html',
		title = "Clips from %s" % thing.title,
		thing = thing,
		clips = clips
	)

@reference.route('/ref_clips/<string:md5>')
def reference_clips(md5):
	"""
	A page made of clips
	"""
	u = Upload.objects.filter(md5=md5).first()
	thing = Thing.objects.filter(files=u).first()
	if not u:
		abort(404)
	# load annotations
	annotations = Reference.objects.filter(upload=u).order_by('pos')
	clips = []

	for a in annotations:
		if a.ref_upload and a.ref_pos:
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor=a.pos)
			if a.ref_pos_end:
				img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (a.ref_pos, a.ref_pos_end, 500)))
			else:
				img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (int(a.ref_pos), int(a.ref_pos)+1, 500)))
			clips.append((link,img,"",a.tags))

	return render_template('reference/clips.html',
		title = "Clips referencing %s" % thing.title,
		thing = thing,
		clips = clips
	)