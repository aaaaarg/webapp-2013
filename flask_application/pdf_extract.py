"""
This is an update over pdf_scraper.py.
It uses poppler libraries and should be significantly faster.
"""
import glob
import os
import subprocess

class Pdf:
	""" Does the work of actually interfacing with PDF files """
	def __init__(self, path):
		self.path = path
		self.meta = self.get_info()
	def get_info(self):
		out = subprocess.check_output(["pdfinfo", self.path])
		return dict([(X.split(':')[0].strip(), ':'.join(X.split(':')[1:]).strip()) for X in out.split('\n') if len(X.strip()) > 2])
	@property
	def npages(self):
		return int(self.meta["Pages"])
	def dump_pages(self):
		content = {}
		for i in range(self.npages):
			content[i+1] = self.dump_page(i+1)
		return content
	def dump_page(self, p):
		#print 'pdftotext', '-nopgbrk', '-f', str(p), '-l', str(p), self.path, '-'
		return subprocess.check_output(['pdftotext', '-nopgbrk', '-f', str(p), '-l', str(p), self.path, '-'])