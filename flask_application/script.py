import datetime, sys, traceback, re
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
			if todo=='things' or todo=='all':
				print 'dropping things index'
				solr.delete(queries=solr.Q(content_type="thing"))
				solr.commit()
				print 'reindexing things'
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
					m.add_to_solr()
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
						solr.commit()
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
		else:
			print 'Skipping...'
	else:
		print "No upload found with the given md5"

class IndexPDFText(Command):
	""" Extracts text from a PDF and indexes it in Solr """
	option_list = (
		Option('--md5', '-m', dest='md5'),
	)
	def run(self, md5):
		if md5:
			u = Upload.objects.filter(md5=md5).first()
			indexUpload(u)
		else:
			for u in Upload.objects().all():
					try:
						indexUpload(u)
					except PDFSyntaxError:
						print '- Skipping... syntax error'
					except PSEOF:
						print '- Skipping... unexplained EOF'