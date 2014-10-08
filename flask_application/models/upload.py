import os, hashlib, unicodedata, re

from bson import ObjectId

from flask_application import app

from werkzeug import secure_filename
from mongoengine.base import ValidationError

from . import db, CreatorMixin, SolrMixin

"""

Uploads will be stored in the directory specified by the UPLOADS_DIR configuration.
The UPLOADS_SUBDIR is for organization, within this specific application.
It means that the filename and directory structure have been done in Calibre-style.
Therefore, the file_path will not include UPLOADS_DIR (which is what can be moved around)
and it will include the UPLOADS_SUBDIR.

So when constructing paths to the file, use the UPLOADS_DIR plus the file_path.
But when moving the file, construct the path with UPLOADS_DIR, UPLOADS_SUBDIR, and any additional path.

"""

class Upload(SolrMixin, CreatorMixin, db.Document):
	"""
	Encapsulates a file that has been uploaded. A base class for various specific types
	"""
	meta = {
		'allow_inheritance': True,
	}
	file_name = db.StringField(max_length=255)
	# this is a filename that is based on other application metadata to standardize filenames for users
	structured_file_name = db.StringField(max_length=255, unique=True)
	# if the file is being saved to an alternative uploads location it can be specified here
	file_path = db.StringField(max_length=512)
	file_size = db.IntField()
	mimetype = db.StringField(max_length=255)
	mimetype_params = db.DictField()
	short_description =db.StringField(max_length=255)
	# precompute some identifiers
	sha1 = db.StringField(max_length=255)
	md5 = db.StringField(max_length=255)

	def delete(self, *args, **kwargs):
		# first remove some references to this thing
		from .thing import Thing
		from .reference import Reference
		ts = Thing.objects.filter(files=self)
		for t in ts:
			t.remove_file(self)
		rs = Reference.objects.filter(upload=self)
		for r in rs:
			r.delete()
		rs = Reference.objects.filter(ref_upload=self)
		for r in rs:
			r.delete()
		super(Upload, self).delete(*args, **kwargs)

	def full_path(self):
		"""
		This is the full path to the file, as determined by configured application UPLOADS_DIR, 
		as well as the file_path and/ or name specific to this upload.
		"""
		if self.file_name is None or self.file_name.strip() == '':
			return None
		if self.file_path is None or self.file_path.strip() == '':
			return os.path.join(app.config['UPLOADS_DIR'], self.file_name)
		if self.file_path.strip()[0:1]=='/':
			# in the rare case that the file_path is absolute, we drop the configured UPLOADS_DIR
			return os.path.join(self.file_path, self.file_name)
		return os.path.join(app.config['UPLOADS_DIR'], self.file_path)


	def set_uploaded_file(self, file):
		"""
		Assumes properties described in werkzeug.datastructures.FileStorage
		Attempts to set all fields
		"""
		self.file_name = secure_filename(file.filename)
		self.structured_file_name = self.unique_structured_file_name()
		self.mimetype = file.mimetype
		self.mimetype_params = file.mimetype_params
		p = self.full_path()
		file.save(p)
		self.file_size = os.path.getsize(p)
		self.compute_hashes()


	def set_file(self, path):
		"""
		Path to a file already on disk somewhere.
		If it isn't within the configured upload directory, then we move it there.
		"""
		# Helps split up path
		def splitpath(path, maxdepth=20):
			( head, tail ) = os.path.split(path)
			return splitpath(head, maxdepth - 1) + [ tail ] if maxdepth and head and head != path else [ head or tail ]

		if os.path.exists(path):
			file_name = os.path.basename(path)
			if app.config['UPLOADS_DIR'] in path:
				# file is already in uploads directory, so don't bother moving it
				file_path = path
			else:
				# file is outside of uploads directory, so we should move it
				new_path = os.path.join(app.config['UPLOADS_DIR'], file_name)
				if not os.path.exists(new_path):
					os.rename(path, new_path)
				file_path = new_path
			# Now set attributes from the file
			self.file_name = os.path.basename(file_path)
			self.structured_file_name = self.unique_structured_file_name()
			self.file_path = os.path.join(*splitpath(file_path)[len(splitpath(app.config['UPLOADS_DIR'])):])
			if not self.file_size:
				self.file_size = os.path.getsize(file_path)
			if not self.mimetype:
				import urllib, mimetypes
				url = urllib.pathname2url(file_path)
				self.mimetype, encoding = mimetypes.guess_type(url)
			self.compute_hashes()
			# save all this new information
			try:
				self.save()
			except ValidationError as e:
				print e.message
				print e.errors


	def set_structured_file_name(self, value):
		"""
		Sets the structured file name
		"""
		usf = self.unique_structured_file_name(value=value)
		self.update(set__structured_file_name=usf)
		self.structured_file_name = usf
		
	def unique_structured_file_name(self, value=None, appendage=0):
		"""
		Generates a unique structured file name
		"""
		from . import Upload
		orig_path, ext = os.path.splitext(self.file_name)
		if value is None:
			value = orig_path
		to_slugify = "%s%s" % (value, ext) if appendage==0 else "%s-%s%s" % (value, appendage, ext)
		slugified = self.slugify(to_slugify)
		if not Upload.objects(structured_file_name=slugified).first():
			return slugified
		else:
			return self.unique_structured_file_name(value=value, appendage=appendage+1)


	def apply_calibre_folder_structure(self, data):
		"""
		Calibre names things in this way: Author Name/Title of Book/Title of Book.xyz
		"""
		def safe_name(str):
			#return "".join([c for c in str if c.isalpha() or c.isdigit() or c==' ']).rstrip()[:64]
			return "".join([c for c in str if c.isalpha() or c.isdigit() or c==' ']).rstrip()

		def splitpath(path, maxdepth=20):
			( head, tail ) = os.path.split(path)
			return splitpath(head, maxdepth - 1) + [ tail ] if maxdepth and head and head != path else [ head or tail ]

		author, title = data
		# Get the original extension
		orig_path, ext = os.path.splitext(self.file_name)
		# Get the parts of the new path
		directory1 = safe_name(author)
		directory2 = safe_name(title)
		filename = "%s%s" % (directory2, ext)
		# put together the new path
		new_path = os.path.join(app.config['UPLOADS_DIR'], app.config['UPLOADS_SUBDIR'], directory1, directory2, filename)
		# Check if there will be a file collision
		incrementer = 1
		while os.path.exists(new_path):
			filename = "%s-%s%s" % (directory2, incrementer, ext)
			new_path = os.path.join(app.config['UPLOADS_DIR'], app.config['UPLOADS_SUBDIR'], directory1, directory2, filename)
			incrementer = incrementer + 1
		# rename to move
		try:
			new_dir = os.path.join(app.config['UPLOADS_DIR'], app.config['UPLOADS_SUBDIR'], directory1, directory2)
			if not os.path.exists(new_dir):
				os.makedirs(new_dir)
			os.rename(self.full_path(), new_path)
			self.file_name = filename
			self.file_path = os.path.join(*splitpath(new_path)[len(splitpath(app.config['UPLOADS_DIR'])):])
			self.set_structured_file_name("%s %s" % (directory1, directory2))
			self.save()
			# @todo: clean up / delete empty directories
		except:
			print "Error: Failed to move file from",self.full_path(),"to",new_path


	def compute_hashes(self):
		BLOCKSIZE = 65536
		hashers = [ ('md5', hashlib.md5()), ('sha1', hashlib.sha1()) ]
		for name, hasher in hashers:
			try:
				with open(self.full_path(), 'rb') as afile:
					buf = afile.read(BLOCKSIZE)
					while len(buf) > 0:
						hasher.update(buf)
						buf = afile.read(BLOCKSIZE)
				setattr(self, name, hasher.hexdigest())
			except:
				print 'Failed to compute hashes for %s', self.file_name


	def slugify(self, s):
		value, ext = os.path.splitext(s)
		_slugify_strip_re = re.compile(r'[^\w\s-]')
		_slugify_hyphenate_re = re.compile(r'[-\s]+')
		if not isinstance(value, unicode):
			value = unicode(value)
		value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
		value = unicode(_slugify_strip_re.sub('', value).strip().lower())
		return "%s%s" % (_slugify_hyphenate_re.sub('-', value), ext)


	def recover_broken_file(self, data):
		"""
		Sometimes the file just gets lost in the uploads directory.
		This recursively crawls the directory to match the file (via hash) and then moves the file
		and resaves the Upload
		"""
		def compute_hash(path):
			BLOCKSIZE = 65536
			md5 = hashlib.md5()
			try:
				with open(path, 'rb') as afile:
					buf = afile.read(BLOCKSIZE)
					while len(buf) > 0:
						md5.update(buf)
						buf = afile.read(BLOCKSIZE)
				return md5.hexdigest()
			except:
				return False

		def safe_name(str):
			#return "".join([c for c in str if c.isalpha() or c.isdigit() or c==' ']).rstrip()[:64]
			return "".join([c for c in str if c.isalpha() or c.isdigit() or c==' ']).rstrip()

		def splitpath(path, maxdepth=20):
			( head, tail ) = os.path.split(path)
			return splitpath(head, maxdepth - 1) + [ tail ] if maxdepth and head and head != path else [ head or tail ]

		def look_for_file(path, the_md5):
			for root, dirs, files in os.walk(path):
				for filename in files:
					p = os.path.join(root, filename)
					md5 = compute_hash(p)
					if md5==the_md5:
						self.file_name = filename
						self.file_path = os.path.join(*splitpath(p)[len(splitpath(app.config['UPLOADS_DIR'])):])
						self.set_structured_file_name(filename)
						self.save()
						return True

		author, title = data
		orig_path, ext = os.path.splitext(self.file_name)
		# Get the parts of the new path
		directory1 = safe_name(author)
		directory2 = safe_name(title)
		newfilename = "%s%s" % (directory2, ext)		
		
		if not self.md5:
			return "bad file!"
		if self.md5==compute_hash(self.full_path()):
			# The file is already a good one
			return "yay! already in the right place!"
		# check author directory first
		found = look_for_file(os.path.join(app.config['UPLOADS_DIR'], app.config['UPLOADS_SUBDIR'], directory1), self.md5)
		# now walk through entire uploads directory, starting with root
		if not found:
			found = look_for_file(app.config['UPLOADS_DIR'], self.md5)
		if found:
			self.apply_calibre_folder_structure(data)
			return "sucessfully moved the file to the right place"
		return "couldn't find the file anywhere :("

	def request_preview(self):
		# requests that a preview be generated
		import datetime
		self.update(set__created_at=datetime.datetime.now())

	def preview(self):
		if self.md5 and 'SCANS_SUBDIR' in app.config:
			preview_path = os.path.join(app.config['SCANS_SUBDIR'], self.md5, "50x72.jpg")
			if os.path.exists(os.path.join(app.config['UPLOADS_DIR'], preview_path)):
				return preview_path
		return False

	def preview_dir(self):
		if self.md5 and 'SCANS_SUBDIR' in app.config:
			preview_path = os.path.join(app.config['SCANS_SUBDIR'], self.md5)
			preview_dir = os.path.join(app.config['UPLOADS_DIR'], preview_path)
			if os.path.exists(preview_dir):
				return preview_dir
		return False

	def add_annotation(self, annotation):
		self.update(add_to_set__annotations=annotation)


	def plaintext(self):
		if self.md5 and 'TXT_SUBDIR' in app.config:
			txt_path = os.path.join(app.config['TXT_SUBDIR'], self.md5, "%s.txt" % self.md5)
			txt_dir = os.path.join(app.config['UPLOADS_DIR'], txt_path)
			if os.path.exists(txt_dir):
				return txt_dir

	def extract_pdf_text(self, format="txt"):
		""" Extracts text from a pdf. Format can be txt or html """
		from pdfminer.pdfparser import PDFParser
		from pdfminer.pdfdocument import PDFDocument
		from pdfminer.converter import HTMLConverter, TextConverter
		from pdfminer.layout import LAParams
		from pdfminer.pdfpage import PDFPage
		from pdfminer.pdfpage import PDFTextExtractionNotAllowed
		from pdfminer.pdfinterp import PDFResourceManager
		from pdfminer.pdfinterp import PDFPageInterpreter
		from pdfminer.pdfdevice import PDFDevice
		from cStringIO import StringIO
		import codecs
		# try and read from file
		retVal = False
		codec = 'ascii'
		if self.md5 and 'TXT_SUBDIR' in app.config:
			txt_dir = os.path.join(app.config['UPLOADS_DIR'], app.config['TXT_SUBDIR'], self.md5)
			txt_path = os.path.join(txt_dir, "%s.%s" % (self.md5, format))
			if os.path.exists(txt_path):
				with codecs.open(txt_path, "r", codec) as f:
					return f.read()
	    # only text and html conversion allowed
			try_path = self.full_path()
			if try_path and os.path.exists(try_path):
				rsrcmgr = PDFResourceManager()
				# create the directory for a cached version of the text file if it doesn't exist
				if not os.path.exists(txt_dir):
						os.makedirs(txt_dir)
				with codecs.open(txt_path, "w", encoding=codec) as fout:
					laparams = LAParams()
					if format=="txt":
						device = TextConverter(rsrcmgr, fout, codec=codec, laparams=laparams)
					elif format=="html":
						device = HTMLConverter(rsrcmgr, fout, codec=codec, laparams=laparams)
					fp = file(try_path, 'rb')
					interpreter = PDFPageInterpreter(rsrcmgr, device)
					password = ""
					maxpages = 0
					caching = True
					pagenos=set()
					for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
						interpreter.process_page(page)
					fp.close()
					device.close()
					fout.close()
					with codecs.open(txt_path, "r", codec) as f:
						content = f.read()
						if not content=="":
							retVal = content
			# make sure this directory is gone if there are not going to be any contents
			if not retVal:
				shutil.rmtree(txt_dir)
		return retVal

	def build_solr(self):
		# I think this will cause major problems when uploads are saved because it triggers a pdf text extraction
		return {}
		
		# first try and extract text
		content = self.extract_pdf_text()
		if not content:
			return {}
		else:
			return {
			'_id' : self.id,
			'content_type' : 'upload',
			'searchable_text': content,
		}


class TextUpload(Upload):
	num_pages = db.IntField()



class UploadManager(object):
	"""
	Handles uploads and delivers an object
	"""

	def set_uploaded_file(self, file, **kwargs):
		"""
		Assumes properties described in werkzeug.datastructures.FileStorage
		Attempts to set all fields
		"""
		if file.mimetype in ['application/pdf', 'application/epub+zip', 'text/plain', 'text/html']:
			u = TextUpload(**kwargs)
		else:
			u = Upload(**kwargs)
		u.set_uploaded_file(file)

		existing = Upload.objects(md5=u.md5).first()
		if existing:
			return existing
		else:
			u.save()
			return u
