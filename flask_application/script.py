import datetime
import sys
import traceback
import re
import os
from unidecode import unidecode
import subprocess
import urllib
import fnmatch
import shutil

from sunburnt.schema import SolrError

from pymongo import MongoClient

from mongoengine.errors import ValidationError

from flask import url_for
from flask.ext.script import Command, Option
from flask.ext.security.utils import encrypt_password
from flask_application import user_datastore, app, tweeter, do_tweets
from flask_application.populate import populate_data
from flask_application.models import db, elastic, User, Role, Thing, Maker, Upload, Reference, Collection, SuperCollection, CollectedThing, Thread, Comment, Queue, TextUpload, Metadata

# pdf extraction
from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.psparser import PSEOF
# other pdf extraction!
from flask_application.pdf_extract import Pdf
# opf writing
from flask_application.helpers import thing2opf, opf2id, opf_date, queryset_batch, ol_metadata

# elasticsearch
from elasticsearch import Elasticsearch
es = Elasticsearch(['http://127.0.0.1:9200/', ])

from twitter import TwitterError

class SetPassword(Command):
   option_list = (
           Option('--id', '-i', dest='id'),
           Option('--password', '-p', dest='pw'),
   )
   def run(self, id, pw):
           if '@' in id:
                u = User.objects.get(email=id)
           else:
                u = User.objects.get(id=id)
           u.password = encrypt_password(pw)
           u.save()


class ImportMetadata(Command):
    def update(self, thing, metadata, identifiers, data):
        if thing:
            thing.update(set__identifier=identifiers)
        if metadata and data:
            metadata.set_ol(data)
            print "Metadata updated! ",thing.id


    def run(self):
        # try with data file
        import csv
        import bson
        from pprint import pprint

        fp = 'flask_application/static/csv/ol_ids.csv'

        with open(fp,'r') as f:
            reader = csv.reader(f, delimiter=',', quotechar='"')
            for row in reader:
                if len(row)==3 and row[0]!='thing_id':
                    thing_id = row[0].strip()
                    try:
                        thing = Thing.objects.get(id=thing_id)
                    except:
                        thing = False
                    if thing:
                        ol_id = row[1].replace('/works/','')
                        isbn = row[2].split(',')[:5]
                        olid_str = "olid:"+ol_id if ol_id else ''
                        isbn_str = "isbn:"+','.join(isbn) if isbn else ''
                        id_str = olid_str + ';' + isbn_str if olid_str or isbn_str else ''
                        try:
                            m = Metadata.objects.get(thing=thing)
                        except:
                            m = Metadata(thing=thing)
                            m.reload()
                        # check if we've already got metadata
                        if not m.ol:
                            data = ol_metadata(ol_id)
                        else:
                            data = False
                            print "Metadata already exists:",thing_id
                        # upate the thing
                        self.update(thing, m, id_str, data)
                    else:
                        print "Skipping unfound thing:", thing_id
                else:
                    print "bad row: ", row


class Tweet(Command):
    option_list = (
        Option('--id', '-i', dest='id'),
    )

    def run(self, id):
        if tweeter and do_tweets:
            try:
                thing = Thing.objects.filter(id=id).first()
                text_part = "%s - %s" % (thing.short_description, thing.title)
                tweeter.PostUpdate("%s %s" % (text_part[:116].encode(
                    'utf8'), url_for('thing.detail', id=id, _external=True)))
            except TwitterError, e:
                print "Twitter Error:"
                print e
                print "%s %s" % (text_part[:116].encode('utf8'), url_for('thing.detail', id=id, _external=True))
            except:
                print "Unexpected error:", sys.exc_info()[0]
                print traceback.print_tb(sys.exc_info()[2])


class GetPath(Command):
    option_list = (
        Option('--md5', '-m', dest='md5'),
    )

    def get_path_from_md5(self, md5):
        u = Upload.objects.filter(md5=md5).first()
        if u:
            print u.full_path()
        else:
            return False

    def run(self, md5):
        return self.get_path_from_md5(md5)


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
            'collections': [str(c.id) for c in Collection.objects.filter(things__thing=t)],
            'index_files': 1,
        }
        es.index(
            index="aaaarg",
            doc_type="thing",
            id=str(t.id),
            body=body)

    def index_maker(self, m):
        """ Indexes a single maker """
        things = Thing.objects.filter(makers__maker=m)
        if things.count() == 0:
            return False
        searchable = ' '.join(
            ["%s %s" % (t.title, t.short_description) for t in things])
        searchable = '%s %s' % (searchable, m.display_name)
        body = {
            'title': m.display_name,
            'searchable_text': searchable,
            'things': [str(t.id) for t in things]
        }
        es.index(
            index="aaaarg",
            doc_type="maker",
            id=str(m.id),
            body=body)

    def index_collection(self, c):
        """ Indexes a single collection """
        if c.accessibility == 'private':
            return {}
        try:
            searchable = ' '.join(["%s %s" % (
                ct.thing.title, ct.thing.format_makers_string()) for ct in c.things if ct])
        except:
            searchable = ''
        searchable = '%s %s %s %s' % (
            searchable, c.title, c.short_description, c.description)
        body = {
            'title': c.title,
            'short_description': c.short_description,
            'description': c.description,
            'searchable_text': searchable,
            'things': [str(ct.thing.id) for ct in c.things]
        }
        es.index(
            index="aaaarg",
            doc_type="collection",
            id=str(c.id),
            body=body)

    def index_upload(self, u, force=False):
        """ Indexes a file upload, if possible; forces the issue, if necessary; update """
        # try to get the first page
        def upload_already_indexed(upload):
            ''' Has the upload already been indexed? Look for page 1 '''
            try:
                p = es.get(index="aaaarg", doc_type="page", id="%s_%s" %
                           (str(upload.id), 1), fields='md5')
                return True
            except:
                return False

        try_path = u.full_path()
        n, e = os.path.splitext(try_path)
        # only handle pdfs
        if not e == '.pdf':
            return False
        # Determine the job
        is_indexed = upload_already_indexed(u)
        needs_extraction = force or not is_indexed
        _illegal_xml_chars_RE = re.compile(
            u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')
        # Try to extract
        if needs_extraction:
            print "Opening", u.structured_file_name, "for extraction"
            try:
                pages = Pdf(try_path).dump_pages()
                num_pages = len(pages)
            except:
                return False
        else:
            try:
                num_pages = Pdf(try_path).npages
            except:
                return False
        # This is the base document
        t = Thing.objects(files=u)[0]
        body = {
            'md5': u.md5,
            'thing': str(t.id),
            'title': t.title,
            'makers': [str(m.maker.id) for m in t.makers],
            'makers_string': t.format_makers_string(),
            'collections': [str(c.id) for c in Collection.objects.filter(things__thing=t)],
            'page_count': len(pages),
            'page': 1,
        }

        if needs_extraction and pages:
            for page_num, content in pages.iteritems():
                if content:
                    print "Page:", page_num
                    id = "%s_%s" % (str(u.id), page_num)
                    try:
                        content = unicode(content, 'utf-8')
                        content = unidecode(content)
                    except:
                        pass
                    # re.sub(_illegal_xml_chars_RE, '?', content)
                    body['searchable_text'] = content
                    body['page'] = page_num
                    es.index(
                        index="aaaarg",
                        doc_type="page",
                        id=id,
                        body=body)
        elif not needs_extraction:
            print "Updating ", num_pages, "pages - extraction not needed."
            for page_num in range(num_pages):  # 0 index, needs to be corrected
                id = "%s_%s" % (str(u.id), page_num + 1)
                body['page'] = page_num + 1
                es.update(
                    index="aaaarg",
                    doc_type="page",
                    id=id,
                    body={'doc': body})

    def index_all_things(self):
        """ Indexes all things """
        batch = -1
        keep_going = True
        while keep_going:
            keep_going = False
            batch += 1
            for t in Thing.objects.skip(batch * self.batch_size).limit(self.batch_size):
                self.index_thing(t)
                keep_going = True

    def index_all_makers(self):
        """ Indexes all makers """
        batch = -1
        keep_going = True
        while keep_going:
            keep_going = False
            batch += 1
            for m in Maker.objects.skip(batch * self.batch_size).limit(self.batch_size):
                self.index_maker(m)
                keep_going = True

    def index_all_collections(self):
        """ Indexes all collections """
        batch = -1
        keep_going = True
        while keep_going:
            keep_going = False
            batch += 1
            for c in Collection.objects.skip(batch * self.batch_size).limit(self.batch_size):
                self.index_collection(c)
                keep_going = True

    def index_all_uploads(self):
        """ Indexes all uploads, thing by thing """
        batch = -1
        keep_going = True
        while keep_going:
            keep_going = False
            batch += 1
            for t in Thing.objects.skip(batch * self.batch_size).limit(self.batch_size):
                for u in t.files:
                    self.index_upload(u, True)
                keep_going = True

    def index_updated_uploads(self, only_once=False):
        """ Indexes all uploads, thing by thing """
        keep_going = True
        while keep_going:
            r = es.search(index="aaaarg", doc_type="thing", body={
                          'query': {'match': {'index_files': 1}}}, fields='title')
            if 'hits' in r and 'hits' in r['hits'] and r['hits']['hits']:
                for t in r['hits']['hits']:
                    try:
                        thing = Thing.objects.get(id=t['_id'])
                        for u in thing.files:
                            self.index_upload(u)
                    except:
                        'Bad thing'
                    es.update(index='aaaarg', doc_type='thing', id=t[
                              '_id'], body={'doc': {'index_files': 0}})
                if only_once:
                    keep_going = False
            else:
                keep_going = False
                print "Nothing needs updating."
        print "Finished!"

    def run(self, do, id):
        self.batch_size = 500
        # Index every thing (quick)
        # index every collection (quick)
        # Index every author (quick)
        # Index every page (slow)
        #ts = Thing.objects.filter(files=self)
        if do == 'maker':
            if id == 'all':
                self.index_all_makers()
            else:
                m = Maker.objects.filter(id=id).first()
                if m:
                    self.index_maker(m)
        if do == 'collection':
            if id == 'all':
                self.index_all_collections()
            else:
                c = Collection.objects.filter(id=id).first()
                if c:
                    self.index_collection(c)
        if do == 'thing':
            if id == 'all':
                self.index_all_things()
            else:
                t = Thing.objects.filter(id=id).first()
                if t:
                    self.index_thing(t)
        if do == 'page':
            if id == 'all':
                self.index_all_uploads()
            elif id == 'updated':
                self.index_updated_uploads()
            elif id == 'some':
                self.index_updated_uploads(True)
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
            if todo == 'things' or todo == 'all':
                print 'dropping things index'
                solr.delete(queries=solr.Q(content_type="thing"))
                solr.commit()
                print 'reindexing things'
                for t in Thing.objects().all():
                    t.add_to_solr(commit=False)
                    if counter == 100:
                        solr.commit()
                        print " 100 done - at ", t.title
                        counter = 0
                    counter += 1
            if todo == 'collections' or todo == 'all':
                print 'dropping collections index'
                solr.delete(queries=solr.Q(content_type="collection"))
                solr.commit()
                print 'reindexing collections'
            if todo == 'makers' or todo == 'all':
                print 'dropping makers index'
                solr.delete(queries=solr.Q(content_type="maker"))
                solr.commit()
                print 'reindexing makers'
                for m in Maker.objects().all():
                    m.add_to_solr(commit=False)
                    if counter == 100:
                        solr.commit()
                        print " 100 done - at ", m.display_name
                        counter = 0
                    counter += 1
            if todo == 'discussions' or todo == 'all':
                print 'dropping discussions index'
                solr.delete(queries=solr.Q(content_type="thread"))
                solr.commit()
                print 'reindexing discussions'
            if todo == 'pages' or todo == 'all':
                print 'dropping pages index'
                solr.delete(queries=solr.Q(content_type="page"))
                solr.commit()
            if todo == 'uploads' or todo == 'all':
                print 'dropping uploads index'
                solr.delete(queries=solr.Q(content_type="upload"))
                solr.commit()


class FixMD5s(Command):
    """ Clears out duplicate uploads (based on md5) """

    def run(self, **kwargs):
        def check_upload(upload):
            t = Thing.objects.filter(files=upload).first()
            if not t:  # the upload isn't being used, so let's delete it
                print "deleting", upload.structured_file_name
                upload.delete()

        def check_md5(md5):
            uploads = Upload.objects.filter(md5=md5)
            if len(uploads) > 1:
                first = None
                for u in uploads:
                    if not first:
                        first = u
                    else:
                        print "deleting", u.structured_file_name
                        Reference.objects(upload=u).update(set__upload=first)
                        Reference.objects(ref_upload=u).update(
                            set__ref_upload=first)
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
        symlink = os.path.join(app.config['UPLOADS_DIR'], app.config[
                               'UPLOADS_MAPDIR'], '%s.pdf' % u.md5)
        if not os.path.exists(symlink):
            try:
                os.symlink(u.full_path(), symlink)
                print 'created: ', u.md5
            except:
                print 'ERROR: ', u.md5
        """
		if force or os.path.exists(symlink):
			os.unlink(symlink)
		try:
			os.symlink(u.full_path(), symlink)
		except:
			pass
		"""
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
        _illegal_xml_chars_RE = re.compile(
            u'[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]')
        print "Opening", u.structured_file_name, "for extraction"
        pages = u.extract_pdf_text(paginated=True)
        page_num = 0
        if pages:
            for content in pages:
                if content:
                    d = {
                        '_id': "%s_%s" % (u.id, page_num),
                        'content_type': 'page',
                        'searchable_text': re.sub(_illegal_xml_chars_RE, '?', content),
                        'md5_s': u.md5,
                    }

                    for k in d:
                        if isinstance(d[k], basestring):
                            d[k] = unidecode(d[k])

                    try:
                        print "- Adding page #", page_num
                        solr.add(d)
                        # solr.commit()
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
            txt_dir = os.path.join(app.config['UPLOADS_DIR'], app.config[
                                   'TXT_SUBDIR'], f.md5)
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

testing_xml = """
<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:identifier opf:scheme="calibre" id="calibre_id">144</dc:identifier>
        <dc:identifier opf:scheme="uuid" id="uuid_id">d6ee9785-cd28-4c86-a8e2-e0924744418c</dc:identifier>
        <dc:title>THEORY AND THE COMMON FROM MARX TO BADIOU</dc:title>
        <dc:creator opf:file-as="McGee, Patrick" opf:role="aut">Patrick McGee</dc:creator>
        <dc:contributor opf:file-as="calibre" opf:role="bkp">calibre (2.47.0) [http://calibre-ebook.com]</dc:contributor>
        <dc:date>2015-12-30T22:46:41+00:00</dc:date>
        <dc:description>Using a method that combines analysis, memoir, and polemic, McGee writes experimentally about a series of thinkers who ruptured linguistic and social hierarchies, from Marx, to Gramsci, to Badiou.</dc:description>
        <dc:identifier opf:scheme="ARG">51c58bfe6c3a0eda0b267600</dc:identifier>
        <dc:language>en</dc:language>
        <meta content="{&quot;Patrick McGee&quot;: &quot;&quot;}" name="calibre:author_link_map"/>
        <meta content="2015-12-30T14:54:44.576569+00:00" name="calibre:timestamp"/>
        <meta content="THEORY AND THE COMMON FROM MARX TO BADIOU" name="calibre:title_sort"/>
    </metadata>
    <guide>
        <reference href="cover.jpg" title="Cover" type="cover"/>
    </guide>
</package>
"""
LIBRARIES_PATH = '/lockers/hmmmmm/collections'


class BuildLibrary(Command):
    """ Converts a collection into a calibre library """
    option_list = (
        Option('--id', '-c', dest='collection_id'),
        Option('--tid', '-t', dest='thing_id'),
    )

    def add_thing_folder_to_library(self, thing, tmp_path):
        thing_dir = os.path.join('/tmp', tmp_path, str(thing.id))
        if not os.path.exists(thing_dir):
            os.makedirs(thing_dir)
        thing2opf(thing, path=os.path.join(thing_dir, 'metadata.opf'))
        preview = thing.preview(filename="x350-0.jpg")
        #preview = 'http://ecx.images-amazon.com/images/I/51fMBpPKSZL._SX331_BO1,204,203,200_.jpg'
        if preview:
            try:
                urllib.urlretrieve(
                    'http://aaaaarg.fail/pages/' + preview, os.path.join(thing_dir, "cover.jpg"))
            except:
                print "Could not generate cover: ", preview
        return thing_dir

    def add_thing_to_library(self, thing, library_path):
        makers = [m.maker.display_name for m in thing.makers]
        makers_str = (' & ').join(makers)
        preview = thing.preview(filename="x350-0.jpg")
        cover = None
        if preview:
            cover = os.path.join('/tmp/', "%s.jpg" % str(thing.id))
            urllib.urlretrieve('http://aaaaarg.fail/pages/' + preview, cover)
        if cover:
            subprocess.call(['calibredb', 'add', '-e', '-I', 'arg:%s' % str(thing.id), '-c',
                             cover, '-a', makers_str, '-t', thing.title, '--library-path=%s' % library_path])
        else:
            subprocess.call(['calibredb', 'add', '-e', '-I', 'arg:%s' % str(thing.id),
                             '-a', makers_str, '-t', thing.title, '--library-path=%s' % library_path])

    def construct_library(self, c):
        library_path = os.path.join(LIBRARIES_PATH, str(c.id))
        for t in c.things:
            print "Adding", t.thing.title
            d = self.add_thing_folder_to_library(t.thing, str(c.id))
            #self.add_thing_to_library(t.thing, library_path)
        subprocess.call(['calibredb', 'add', '-r', '--library-path=%s' %
                         library_path, os.path.join('/tmp', str(c.id))])
        # now move covers
        for root, dirnames, filenames in os.walk(library_path):
            for filename in fnmatch.filter(filenames, '*.opf'):
                with open(os.path.join(root, filename), 'r') as f:
                    id = opf2id(f.read())
                    cover = os.path.join('/tmp', str(c.id), id, 'cover.jpg')
                    if os.path.exists(cover):
                        dest = os.path.join(root, 'cover.jpg')
                        print 'Moving ', cover, 'to', dest
                        shutil.move(cover, dest)

    def run(self, collection_id, thing_id):
        if collection_id:
            c = Collection.objects.filter(id=collection_id).first()
            self.construct_library(c)
        elif thing_id:
            t = Thing.objects.filter(id=thing_id).first()
            m = Metadata.objects.get(thing=t)
            m.set_opf(testing_xml)


class AddToIpfsTest(Command):
    option_list = (
        Option('--do', '-d', dest='letter'),
    )

    def run(self, letter):
        def char_range(c1, c2):
            """Generates the characters from `c1` to `c2`, inclusive."""
            for c in xrange(ord(c1), ord(c2) + 1):
                yield chr(c)

        if not letter:
            for letter in char_range('a', 'z'):
                self.do_letter(letter)
        else:
            self.do_letter(letter)

    def do_letter(self, letter):
        print "--- Starting %s ---" % letter
        test_uploads = Upload.objects.filter(
            file_name__istartswith=letter, ipfs__exists=False)
        print "Adding some test uploads to IPFS..."

        for upload in queryset_batch(test_uploads, 50):
            try:
                upload.ipfs_add()
                print "Successfully added %s" % (upload.full_path(),)
            except Exception, e:
                print "Error adding %s: %s" % (upload.full_path(), e)


class AddToIpfsTest(Command):

    option_list = (
        Option('--upload', '-u', dest='upload_id'),
        Option('--thing', '-t', dest='thing_id'),
        Option('--letter', '-l', dest='letter'),
    )

    def run(self, upload_id, thing_id, letter):

        def char_range(c1, c2):
            """Generates the characters from `c1` to `c2`, inclusive."""
            for c in xrange(ord(c1), ord(c2) + 1):
                yield chr(c)

        if thing_id:
            thing = Thing.objects.get(id=thing_id)
            uploads = thing.files
            self.do_uploads(uploads)
        elif upload_id:
            uploads = Upload.objects.filter(id=upload_id)
            self.do_uploads(uploads)
        elif letter:
            self.do_letter(letter)
        else:
            for letter in char_range('a', 'z'):
                self.do_letter(letter)

    def do_uploads(self, uploads):
        print "Adding some test uploads to IPFS..."
        for upload in uploads:
            try:
                upload.ipfs_add()
                print "Successfully added %s" % (upload.full_path(),)
            except Exception, e:
                print "Error adding %s: %s" % (upload.full_path(), e)

    def do_letter(self, letter):
        print "====== %s =====" % letter
        uploads = Upload.objects.filter(
            file_name__istartswith=letter, ipfs__exists=False)
        uploads = queryset_batch(uploads, 50)
        self.do_uploads(uploads)


class ProcessIpfsAddOutput(Command):
  """
  Store the hashes from the output of "ipfs add -r" in the Upload records.
  When a dumpfile is given it dumps all the hashes (one per line) into a file
  """

  option_list = (
    Option(dest='filename'),
    Option('--dump', '-d', dest='dumpfile'),
  )

  def run(self, filename, dumpfile=None):
    if not os.path.exists(filename):
      print(u"ERROR: file doesn't exist: %s" % (filename,))
      return

    with open(filename) as f:
      if dumpfile:
        with open(dumpfile, 'w') as fo:
          for line in f:
            self.dump_line(line, fo)
      else:  
        for line in f:
          self.process_line(line)


  def dump_line(self, line, f):
    line = line.strip()
    pieces = line.split(" ", 2)
    if pieces[0] == "added":
      hash = pieces[1]
      f.write("%s\n" % hash)

    def process_line(self, line):
        line = line.strip()
        pieces = line.split(" ", 2)
        if pieces[0] == "added":
            hash = pieces[1]
            path = pieces[2]
            full_path = os.path.join(app.config.get('UPLOADS_DIR'), path)
            if os.path.isfile(full_path):
                u = None
                try:
                    results = Upload.objects.filter(file_path=path, ipfs=None)
                    if results:
                        u = results[0]
                except Upload.DoesNotExist, e:
                    print(
                        u"WARNING: Couldn't find Upload model object for path=%s" % (path,))
                if u:
                    print(u"Updating %s %s with hash %s" %
                          (u.id, u.file_path, hash))
                    u.ipfs = hash
                    u.save()
        else:
            try:
                print(u"Couldn't parse line: %s" % (line,))
            except:
                print("Couldn't parse line and error in printing line")


class FixFilesMigration(Command):
    """Migrates old files into new structure"""

    def run(self, **kwargs):
        import csv
        # for pre-2014 data
        client = MongoClient()
        db = client.aaaart
        legacy_users = db.people
        # get a handle on pre-2013 data
        drupal_6_data_csv = os.path.join(
            app.config['UPLOADS_DIR'], 'drupal-6-files.csv')
        legacy_data_map = {}
        with open(drupal_6_data_csv, 'rb') as f:
            reader = csv.reader(f)
            legacy_data = list(reader)
            for d in legacy_data[1:]:
                parts = d[0].split(';')
                if len(parts) > 5:
                    file_size = parts[5]
                    user_id = parts[1]
                    filename = parts[2]
                    try:
                        legacy_user = legacy_users.find_one(
                            {"grr_id": int(user_id)})
                        if legacy_user and '_id' in legacy_user:
                            legacy_data_map[int(file_size)] = (
                                legacy_user['_id'], filename)
                    except:
                        print "skipping adding to legacy data map:", parts
        print "legacy map has size: ", len(legacy_data_map)
        empty_count = 0
        fixed_count = 0
        for old_thing in db.images.find(timeout=False):
            for f in old_thing['files']:
                if not f['uploader']:
                    empty_count = empty_count + 1
                else:
                    continue  # its not empty so don't handle it
                if not f['size'] in legacy_data_map:
                    continue  # we don't have the old data either, so we can't handle it
                try:
                    sha1 = f['sha1'].encode(
                        'utf-8').strip() if 'sha1' in f else None
                except:
                    sha1 = None

                existing = Upload.objects(sha1=sha1).first() if sha1 else None
                if existing:
                    if not f['uploader']:
                        if f['size'] in legacy_data_map:
                            try:
                                fixed_count = fixed_count + 1
                                curr_user = User.objects.get(
                                    id=str(legacy_data_map[f['size']][0]))  # curr user
                                existing.creator = curr_user
                                existing.save()
                                print existing.structured_file_name, "should now be assigned to ", curr_user.email
                            except:
                                print "Can't associate %s with a user because user %s doesn't exist in new database" % (f['name'], str(legacy_data_map[f['size']][0]))
                                # print f
                        else:
                            print "can't find ", f['size']
                        # print "The uploader is empty for: ", f['name']
                else:
                    print f['name'], "doesn't seem to exist in 2014- database"
            if empty_count % 1000 == 1:
                print "There are %s bad files and this script fixed %s of them." % (empty_count, fixed_count)
        print "There were %s bad files and this script fixed %s of them." % (empty_count, fixed_count)
