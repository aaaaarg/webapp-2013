#!/usr/bin/env python

import datetime, os, rfc3987, re
from math import floor

from flask import Blueprint, request, redirect, flash, url_for, render_template, send_file, abort, jsonify
from flask.ext.security import (login_required, roles_required, roles_accepted, current_user)
from flask_application import app

from ..models import *

compiler = Blueprint('compiler', __name__, url_prefix='/compiler')

@compiler.route('/create', methods= ['GET', 'POST'])
def create():
	m = request.args.get('mode', None)
	v = request.args.get('value', None)

	if not m and not v:
		user_id = current_user.get_id()
		annotations = Reference.objects.filter(creator=user_id).order_by('-created_at')
		# if there are no annotations this way, then just fetch recent ones
		if not annotations:
			annotations = Reference.objects(pos_end__gt=0).order_by('-created_at').limit(20)
	elif m=='tag' and v is not None:
		annotations = Reference.objects.filter(tags=v).order_by('-created_at')
	elif m=='recent':
		annotations = Reference.objects(pos_end__gt=0).order_by('-created_at').limit(20)
	
	clips = build_clips(annotations)
	return render_template('compiler/create.html',
		title = "compiler",
		clips = clips
	)


@compiler.route('/create/from/search', methods= ['GET', 'POST'])
def create_from_search():
	query = request.args.get('query', "")
	num = 100
	start = 0
	content = ""

	if not query=="":
		#results = solr.query(content_type="page", text=query).paginate(start=start, rows=num).highlight("searchable_text", snippets=3, maxAnalyzedChars=-1).execute()
		#query_tokens = query.split()
		#combined = 'AND '.join(query_tokens)
		#new_query = "'%s'~%d" % (combined, len(query_tokens))
		new_query = "%s" % query
		the_query = solr.query(searchable_text=new_query).filter(content_type="page").filter_exclude(md5_s="7dbf4aee8eb2b19197fe62913e15dda5").sort_by("-score").paginate(start=start, rows=num)
		results = the_query.execute()
		# Build list of results 
		pdf_path = ''
		last_md5 = None
		for result in results:
			if '_id' in result:
				# id[0] is the upload id, id[1] is upload page
				md5 = result['md5_s']
				id = str(result['_id']).split('_')
				if md5 and len(id)==2:
					if md5==last_md5:
						pdf_path = '%s,%s' % (pdf_path, id[1])
					else:
						pdf_path = '%s/%s/%s' % (pdf_path, md5, id[1])
					last_md5 = md5
	
	if pdf_path=='':
		return 'There were no results!'
	else:
		return url_for('reference.preview', filename='compile%s/pdf.pdf' % pdf_path, _external=True)


def build_clips(annotations):
	""" With a result set of annotations, this will build the clips list for display """
	clips = []
	for a in annotations:
		if a.pos_end:
			u = a.upload
			t = a.thing
			y1 = int(a.pos)
			y2 = int(a.pos_end)
			link = url_for("reference.figleaf", md5=a.upload.md5, _anchor='%s-%s' % (a.pos, a.pos_end))
			img = url_for("reference.preview", filename=u.preview(filename='%s-%sx%s.jpg' % (y1, y1, 75)))
			#img = img.replace('/pages/','http://127.0.0.1:8484/')
			page_count = y2 - y1 + 1
			url_part = '%s.pdf/%s-%s/' % (a.upload.md5, y1, y2) if y2>y1 else '%s.pdf/%s/' % (a.upload.md5, y1)
			title = t.title
			clips.append((link,img,title,a.note,page_count, url_part))
	return clips