#!/usr/bin/env python

import datetime, os, rfc3987, re
from math import floor
from PIL import Image

from flask import Blueprint, request, redirect, flash, url_for, render_template, send_file, abort, jsonify
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from flask_application import app
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
	

@reference.route('/clip/<string:md5>/<string:boundaries>.jpg')
def clip(md5, boundaries):
	'''
	Serves an image excerpt pages, with clipping boundaries defined
	(for now, page height is hardcoded as 1000, so hacky bits reflect that)
	'''
	lg_filename_format = '1024x-%s.jpg'
	clip_dir = os.path.join(app.config['UPLOADS_DIR'], app.config['CLIP_CACHE'], md5)
	clip_path = os.path.join(clip_dir, '%s.jpg' % boundaries)
	if os.path.exists(clip_path):
		return send_file(clip_path)
	# Get the boundaries (expects something like 1.11-2.04)
	bounds = boundaries.split('-')
	if len(bounds)==2:
		try:
			(top, bot) = (float(bounds[0]), float(bounds[1]))
		except ValueError:
			abort(404)
	# Now try and load the file
	u = Upload.objects.get_or_404(md5=md5)
	preview_dir = u.preview_dir()
	if preview_dir:
		def compute_y(y, w):
			return int(float(w)*y*10/7)
		# Loads a clip of a page with fr (top) and to (bottom)
		def load_clip(d, fr, to):
			page_path = os.path.join(d, lg_filename_format%int(fr))
			if os.path.exists(page_path):
				im = Image.open(page_path)
				w, h = im.size
				if int(to)>int(fr):
					to = int(fr) + 1
				# hackish computation of image crop based on how JS addressing is done (still buggy at bottom)
				return im.crop((0, compute_y(fr-int(fr), w), w, min(compute_y(to-int(fr), w), h) ))
				#return im.crop((0, int(1000*(fr-int(fr))), w, int(1000*(to-int(fr)))))
			return False

		im = load_clip(preview_dir, top, bot)
		if not im:
			return 'Sorry'
		if int(bot)-int(top)==1:
			im2 = load_clip(preview_dir, int(bot), bot)
			if im2:
				w1, h1 = im.size
				w2, h2 = im2.size
				new_im = Image.new('RGB', (max(w1,w2),h1 + h2))
				new_im.paste(im, (0,0))
				new_im.paste(im2, (0,h1))
				im = new_im
			print 'another'
			# the clip spans 2 pages so we paste them together
		# Save the clip
		if not os.path.exists(clip_dir):
			os.makedirs(clip_dir)
		im.save(clip_path)
		# Serve it
		return send_file(clip_path) 
	return 'Sorry!'


@reference.route('/clips/<string:md5>')
@reference.route('/clips/<string:md5>/<user_id>')
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
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor=a.pos)
			if a.pos_end:
				img = url_for("reference.clip", md5=a.upload.md5, boundaries="%s-%s" % (a.pos, a.pos_end))
				clips.append((link,img,a.note))

	return render_template('reference/clips.html',
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
				img = url_for("reference.clip", md5=a.ref_upload.md5, boundaries="%s-%s" % (a.ref_pos, a.ref_pos_end))
			else:
				img = url_for("reference.clip", md5=a.ref_upload.md5, boundaries="%s-%s" % (int(a.ref_pos), int(a.ref_pos)+1))
			clips.append((link,img,""))

	return render_template('reference/clips.html',
		thing = thing,
		clips = clips
	)