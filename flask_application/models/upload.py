import json
import os, hashlib, unicodedata, re
import stdnum.isbn
import subprocess

from bson import ObjectId

from flask_application import app

from werkzeug import secure_filename
from mongoengine.base import ValidationError

import ipfsApi

import codecs

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
	# ipfs (InterPlanetary File System) hash id
	ipfs = db.StringField(max_length=255)
	ipfs_wrapped_dir_hash = db.StringField(max_length=255)

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
			s = "".join([c for c in str if c.isalpha() or c.isdigit() or c==' ']).rstrip()
			return unicodedata.normalize('NFKD', unicode(s)).encode('ascii','ignore')

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
			# create symbolid link from flat directory to file
			symlink = os.path.join(app.config['UPLOADS_DIR'], app.config['UPLOADS_MAPDIR'], '%s.pdf' % self.md5)
			if os.path.exists(symlink):
				os.unlink(symlink)
			os.symlink(new_path, symlink)
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

	def preview(self, w=50, h=72, c=20, filename=None):
		if self.mimetype=="application/pdf" or os.path.splitext(self.file_name)[1]=='.pdf':
			if not filename:
				return os.path.join('%s.pdf' % self.md5, '%sx%sx%s.jpg' % (w,h,c))
			else:
				return os.path.join('%s.pdf' % self.md5, filename)
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


	def extract_pdf_text(self, format="txt", paginated=False):
		""" Extracts text from a pdf. Format can be txt or html """
		from flask_application.pdf_scraper import get_pages
		if self.md5 and 'TXT_SUBDIR' in app.config:
			codec = 'utf-8'
			txt_dir = os.path.join(app.config['UPLOADS_DIR'], app.config['TXT_SUBDIR'], self.md5)
			txt_path = os.path.join(txt_dir, "%s.%s" % (self.md5, format))
			if os.path.exists(txt_path):
				if paginated:
					return False
				with open(txt_path, "r") as f:
					return f.read()
			try_path = self.full_path()
			# Only handle pdfs (with pdf extension)
			n, e = os.path.splitext(try_path)
			if not e=='.pdf':
				return False
			if try_path and os.path.exists(try_path):
				try:
					pages = get_pages(try_path)
				except:
					return False
				if not pages:
					return False
				everything = "".join(pages)
				if not os.path.exists(txt_dir):
					os.makedirs(txt_dir)
				with open(txt_path, "w") as fout:
					fout.write(everything)
				if paginated:
					return pages
				else:
					return everything

	def find_isbns(self):
		""" Looks through the extracted text to see if an ISBN can be discovered """
		def normalize_isbn(value):
			return ''.join([s for s in value if s.isdigit() or s == 'X'])
		
		text = self.extract_pdf_text()
		matches = re.compile('\d[\d\-X\ ]+').findall(text)
		matches = [normalize_isbn(value) for value in matches]
		isbns = [isbn for isbn in matches if stdnum.isbn.is_valid(isbn)
			and len(isbn) in (10, 13)
			and isbn not in (
			'0' * 10,
			'0' * 13,
		)]	
		return isbns[0]	if isbns else None


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

	def ipfs_add(self):
		"""
		Adds this upload to ipfs. Raises exceptions on failures.
		"""
		if os.path.exists(self.full_path()):
			api = ipfsApi.Client('127.0.0.1', 5001)

			# chdir so that we only pass the base filename to Client.add();
			# if you pass in a full path, it loses the filename when it wraps it
			# in a directory
			origdir = os.getcwd()
			os.chdir(os.path.dirname(self.full_path()))

			error = None
			try:
				# encode to utf8 or urllib will raise error inside Client.add()
				filename = self.file_name.encode('utf8')

				# "-w" option wraps the file in a directory so we can generate a nicer url.
				# There doesn't seem to be a way to tell ipfs to use a different filename
				# (it's be better to use structured_file_name) than disk filename
				response = api.add(filename, opts={'w': True})
			except Exception, e:
				error = e
			finally:
				os.chdir(origdir)

			if not error:
				# response isn't a python object, but a string. weird.
				lines = [line for line in response.split("\n") if line]

				for line in lines:
					d = json.loads(line)
					if d['Name'] == '':
						self.ipfs_wrapped_dir_hash = d['Hash']
					else:
						# TODO: response mangles UTF8 filenames, causing
						# d['Name'] != filename. so we avoid comparing and just assume
						# it's the hash for the file, which works as long as we do one
						# file at a time. Not sure if this is a bug in
						# go-ipfs or in ipfsApi.
						self.ipfs = d['Hash']
				self.save()
			else:
				raise Exception("error calling Client.add(): %s" % (error,))
		else:
			raise Exception("ipfs_add couldn't add non-existent file: %s" %(self.full_path(),))

	def ipfs_accessible(self):
		"""
		:return: True if this upload can be downloaded via ipfs
		"""
		test_case = re.match("^[A-D]", self.file_name.upper()) is not None
		return test_case and app.config.get("IPFS_ENABLED", False)

	def ipfs_http_link(self):
		"""
		:return: string of ipfs download link
		"""
		host = app.config.get('IPFS_HTTP_GATEWAY_HOST')
		path = self.file_path[len(app.config.get('UPLOADS_SUBDIR')):]
		return "http://%s/ipns/%s%s" % (host, app.config.get('IPNS_ROOT_HASH'), path)


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
