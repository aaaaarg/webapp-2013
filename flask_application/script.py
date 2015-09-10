import datetime, sys, traceback, re, os
from unidecode import unidecode

from sunburnt.schema import SolrError

from pymongo import MongoClient

from mongoengine.errors import ValidationError

from flask.ext.script import Command, Option
from flask.ext.security.utils import encrypt_password
from flask_application import user_datastore, app
from flask_application.populate import populate_data
from flask_application.models import db, solr, User, Role, Thing, Maker, Upload, Reference, Collection, SuperCollection, CollectedThing, Thread, Comment, Queue, TextUpload

# pdf extraction
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSEOF
# other pdf extraction!
from flask_application.pdf_extract import Pdf 

# elasticsearch
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://127.0.0.1:9200/',])

class ESIndex(Command):
	option_list = (
		Option('--do', '-d', dest='do'),
		Option('--id', '-i', dest='id'),
	)

	""" Elastic search index """
	def index_thing(self, t):
		""" Indexes a single thing """
		body = {
			'title': t.title,
			'short_description': t.short_description,
			'description': t.description,
			'makers': [str(m.maker.id) for m in t.makers],
			'makers_string': t.format_makers_string(),
			'makers_sorted': t.makers_sorted,
			'collections' : [str(c.id) for c in Collection.objects.filter(things__thing=t)]
		}
		es.index(
			index="aaaarg", 
			doc_type="thing", 
			id=str(t.id), 
			body=body)

	def index_maker(self, m):
		""" Indexes a single maker """
		things = Thing.objects.filter(makers__maker=m)
		if things.count()==0:
			return False
		searchable = ' '.join(["%s %s" % (t.title, t.short_description) for t in things])
		searchable = '%s %s' % (searchable, m.display_name)
		body = {
			'title': m.display_name,
			'searchable_text': searchable,
			'things' : [str(t.id) for t in things]
		}
		es.index(
			index="aaaarg", 
			doc_type="maker", 
			id=str(m.id), 
			body=body)

	def index_collection(self, c):
		""" Indexes a single collection """
		if c.accessibility=='private':
			return {}
		searchable = ' '.join(["%s %s" % (ct.thing.title, ct.thing.format_makers_string()) for ct in c.things])
		searchable = '%s %s %s %s' % (searchable, c.title, c.short_description, c.description)
		body = {
		'title': c.title,
		'short_description': c.short_description,
		'description': c.description,
		'searchable_text': searchable,
		'things' : [str(ct.thing.id) for ct in c.things]
		}
		es.index(
			index="aaaarg", 
			doc_type="collection", 
			id=str(c.id), 
			body=body)


	def index_upload(self, u, force=False):
		""" Indexes a file upload, if possible; forces the issue, if necessary """
		# try to get the first page
		try:
			p = es.get(index="aaaarg", doc_type="page", id="%s_%s" %(str(u.id),1))
			print u.structured_file_name, "is already indexed (found the first page)"
		except:
			_illegal_xml_chars_RE = re.compile(u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')
			print "Opening",u.structured_file_name,"for extraction"
			try_path = u.full_path()
			n,e = os.path.splitext(try_path)
			# only handle pdfs
			if not e=='.pdf':
				return False
			# Try to index
			try:
				pages = Pdf(try_path).dump_pages()
			except:
				return False
			if pages:
				t = Thing.objects(files=u)[0]
				body = {
					'searchable_text': '',
					'md5': u.md5,
					'thing': str(t.id),
					'title': t.title,
					'makers': [str(m.maker.id) for m in t.makers],
					'makers_string': t.format_makers_string(),
					'collections': [str(c.id) for c in Collection.objects.filter(things__thing=t)],
					'page_count': len(pages),
					'page': page_num,
				}
				for page_num, content in pages.iteritems():
					if content:
						print "Page:",page_num
						id = "%s_%s" % (str(u.id), page_num)
						body['searchable_text'] = re.sub(_illegal_xml_chars_RE, '?', content)
						body['page'] = page_num
						es.index(
							index="aaaarg", 
							doc_type="page", 
							id=id, 
							body=body)

	def index_all_things(self):
		""" Indexes all things """
		batch = -1
		keep_going = True
		while keep_going:
			keep_going = False
			batch += 1
			for t in Thing.objects.skip(batch*self.batch_size).limit(self.batch_size):
				self.index_thing(t)
				keep_going = True

	def index_all_makers(self):
		""" Indexes all makers """
		batch = -1
		keep_going = True
		while keep_going:
			keep_going = False
			batch += 1
			for m in Maker.objects.skip(batch*self.batch_size).limit(self.batch_size):
				self.index_maker(m)
				keep_going = True

	def index_all_collections(self):
		""" Indexes all collections """
		batch = -1
		keep_going = True
		while keep_going:
			keep_going = False
			batch += 1
			for m in Collection.objects.skip(batch*self.batch_size).limit(self.batch_size):
				self.index_collection(c)
				keep_going = True

	def index_all_uploads(self):
		""" Indexes all uploads, thing by thing """
		for t in Thing.objects().all():
			for u in t.files:
				self.index_upload(u)

	def run(self, do, id):
		self.batch_size = 500
		# Index every thing (quick)
		# index every collection (quick)
		# Index every author (quick)
		# Index every page (slow)
		#ts = Thing.objects.filter(files=self)
		if do=='maker':
			if id=='all':
				self.index_all_makers()
			else:
				m = Maker.objects.filter(id=id).first()
				if m:
					self.index_maker(m)
		if do=='collection':
			if id=='all':
				self.index_all_collections()
			else:
				c = Collection.objects.filter(id=id).first()
				if c:
					self.index_collection(c)
		if do=='thing':
			if id=='all':
				self.index_all_things()
			else:
				t = Thing.objects.filter(id=id).first()
				if t:
					self.index_thing(t)
		if do=='page':
			if id=='all':
				self.index_all_uploads()
			else:
				t = Thing.objects.filter(id=id).first()
				if t:
					for u in t.files:
						self.index_upload(u)

class ResetDB(Command):
  """Drops all tables and recreates them"""
  def run(self, **kwargs):
    for m in [User, Role, Collection, Thing, Maker, Thread, Queue]:
      m.drop_collection()

class PopulateDB(Command):
  """Fills in predefined data into DB"""
  def run(self, **kwargs):
    populate_data()

class SolrReindex(Command):
	"""Drops one or more content types from solr"""
	option_list = (
		Option('--do', '-d', dest='todo'),
	)
	def run(self, todo):
		if todo:
			counter = 0
			if todo=='things' or todo=='all':
				print 'dropping things index'
				solr.delete(queries=solr.Q(content_type="thing"))
				solr.commit()
				print 'reindexing things'
				for t in Thing.objects().all():
					t.add_to_solr(commit=False)
					if counter==100:
						solr.commit()
						print " 100 done - at ", t.title
						counter = 0
					counter += 1
			if todo=='collections' or todo=='all':
				print 'dropping collections index'
				solr.delete(queries=solr.Q(content_type="collection"))
				solr.commit()
				print 'reindexing collections'
			if todo=='makers' or todo=='all':
				print 'dropping makers index'
				solr.delete(queries=solr.Q(content_type="maker"))
				solr.commit()
				print 'reindexing makers'
				for m in Maker.objects().all():
					m.add_to_solr(commit=False)
					if counter==100:
						solr.commit()
						print " 100 done - at ", m.display_name
						counter = 0
					counter += 1
			if todo=='discussions' or todo=='all':
				print 'dropping discussions index'
				solr.delete(queries=solr.Q(content_type="thread"))
				solr.commit()
				print 'reindexing discussions'
			if todo=='pages' or todo=='all':
				print 'dropping pages index'
				solr.delete(queries=solr.Q(content_type="page"))
				solr.commit()
			if todo=='uploads' or todo=='all':
				print 'dropping uploads index'
				solr.delete(queries=solr.Q(content_type="upload"))
				solr.commit()


class FixMD5s(Command):
	""" Clears out duplicate uploads (based on md5) """
	def run(self, **kwargs):
		def check_upload(upload):
			t = Thing.objects.filter(files=upload).first()
			if not t: # the upload isn't being used, so let's delete it
				print "deleting", upload.structured_file_name
				upload.delete()
		def check_md5(md5):
			uploads = Upload.objects.filter(md5=md5)
			if len(uploads)>1:
				first = None
				for u in uploads:
					if not first:
						first = u
					else:
						print "deleting", u.structured_file_name
						Reference.objects(upload=u).update(set__upload=first)
						Reference.objects(ref_upload=u).update(set__ref_upload=first)
						u.delete()

		# purge uploads that are not in use
		uploads = Upload.objects.all()
		print "CHECKING EMPTIES"
		for u in uploads:
			check_upload(u)
		md5s = Upload.objects.distinct('md5')
		print "CHECKING MD5"
		for md5 in md5s:
			check_md5(md5)


class UploadSymlinks(Command):
	""" Creates symlinks for all uploads """
	option_list = (
		Option('--md5', '-m', dest='md5'),
	)
	# create the symlink
	def do_symlink(self, u, force=False):
		symlink = os.path.join(app.config['UPLOADS_DIR'], app.config['UPLOADS_MAPDIR'], '%s.pdf' % u.md5)
		if force or os.path.exists(symlink):
			os.unlink(symlink)
		try:
			os.symlink(u.full_path(), symlink)
		except:
			pass
	# main run
	def run(self, md5):
		if md5:
			u = Upload.objects.filter(md5=md5).first()
			if u:
				self.do_symlink(u, force=True)
		else:
		# purge uploads that are not in use
			uploads = Upload.objects.all()
			for u in uploads:
				self.do_symlink(u)

def indexUpload(u):
	""" Attempts to extract text from an uploaded PDF and index in Solr """
	if u:
		_illegal_xml_chars_RE = re.compile(u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')
		print "Opening",u.structured_file_name,"for extraction"
		pages = u.extract_pdf_text(paginated=True)
		page_num = 0
		if pages:
			for content in pages:
				if content:
					d = {
						'_id' : "%s_%s" % (u.id, page_num),
						'content_type' : 'page',
						'searchable_text': re.sub(_illegal_xml_chars_RE, '?', content),
						'md5_s': u.md5,
					}
					
					for k in d:
						if isinstance(d[k], basestring):
							d[k] = unidecode(d[k])				

					try:
						print "- Adding page #",page_num
						solr.add(d)
						#solr.commit()
					except SolrError as e:
						print "SolrError: ", e
					except:
						print "Unexpected error:", sys.exc_info()[0]
						print traceback.print_tb(sys.exc_info()[2])
						print d
				else:
					print "- No text could be extracted so this page will not be indexed"
				# incrememnt the page number
				page_num += 1
			try:
				print "- Committing!"
				solr.commit()
			except SolrError as e:
				print "SolrError: ", e
			except:
				print "Unexpected error:", sys.exc_info()[0]
				print traceback.print_tb(sys.exc_info()[2])
				print d
		else:
			print 'Skipping...'
	else:
		print "No upload found with the given md5"

class IndexPDFText(Command):
	""" Extracts text from a PDF and indexes it in Solr """
	option_list = (
		Option('--md5', '-m', dest='md5'),
		Option('--coll', '-c', dest='coll'),
	)
	def run(self, md5, coll):
		if md5:
			u = Upload.objects.filter(md5=md5).first()
			indexUpload(u)
		elif coll:
			c = Collection.objects.filter(id=coll).first()
			for ct in c.things:
				for u in ct.thing.files:
					indexUpload(u)
		else:
			for u in Upload.objects().order_by('-created_at').all():
					try:
						indexUpload(u)
					except PDFSyntaxError:
						print '- Skipping... syntax error'
					except PSEOF:
						print '- Skipping... unexplained EOF'

class ExtractISBN(Command):
	""" Extracts text from a PDF and indexes it in Solr """
	option_list = (
		Option('--id', '-t', dest='thing_id'),
	)
	def extract(self, t):
			print t.title
			for f in t.files:
				txt_dir = os.path.join(app.config['UPLOADS_DIR'], app.config['TXT_SUBDIR'], f.md5)
				txt_path = os.path.join(txt_dir, "%s.%s" % (f.md5, 'txt'))
				if os.path.exists(txt_path):
					print f.find_isbns()

	def run(self, thing_id):
			if thing_id:
				t = Thing.objects.filter(id=thing_id).first()
				self.extract(t)
			else:
				things = Thing.objects.all()
				for t in things:
					self.extract(t)
				
				

