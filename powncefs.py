#!/usr/bin/env python

"""
PownceFS 0.2
Richard Crowley
2008-03-19

http://github.com/rcrowley/powncefs/

This work is licensed under the Creative Commons Attribution-Share Alike
3.0 Unported License. To view a copy of this license, visit
http://creativecommons.org/licenses/by-sa/3.0/ or send a letter to
Creative Commons, 171 Second Street, Suite 300, San Francisco,
California, 94105, USA.
"""

# TTL for API calls (seconds)
#   This is set to 45 minutes right now because the S3 URLs expire in 1 hour
#   and it's always nice to have some breathing room
API_TTL = 60 * 45

import os, stat, sys, fcntl, time
import posix
from errno import *

import fuse
from fuse import Fuse
fuse.fuse_python_api = (0, 2)

fuse.feature_assert('stateful_files', 'has_init')

import urllib2
import oauth.oauth as oauth
import api

import logging

def _inode():
	"""
	A generator for making unique inode numbers
	"""
	i = 0
	while True:
		i += 1
		yield i
inode = _inode().next

class PownceFS(Fuse):
	"""
	Fuse filesystem for your Pownce friends and all their files
	"""

	def __init__(self, *args, **kw):
		Fuse.__init__(self, *args, **kw)

		# Auth with Pownce unless we have stored credentials
		try:
			f = open('%s/.powncefs/auth' % os.path.expanduser('~'), 'r')
			self.token = oauth.OAuthToken.from_string(f.read())
			f.close()
		except Exception, e:
			print e
			self.token = api.auth()
			f = open('%s/.powncefs/auth' % os.path.expanduser('~'), 'w')
			f.write(str(self.token))
			f.close()

		# Prime the filesystem tree
		self.tree = PownceFS.Base(self.token)
		self.tree.fetch()

	def _find(self, path):
		"""
		Find the given path by walking through the stored tree
		"""

		# The root node
		if '/' == path:
			return self.tree

		parts = path[1:].split('/')

		# A user
		if 1 == len(parts):
			return self.tree.get(parts[0])

		# A file
		elif 2 == len(parts):
			node = self.tree.get(parts[0])
			if node is None:
				return None
			else:
				return node.get(parts[1])

		else:
			return None

	def getattr(self, path):
		logging.debug('getattr %s' % path)
		node = self._find(path)
		if node is None:
			return -1
		else:
			return node.getattr()

	def access(self, path, mode):
		return 0

	def readdir(self, path, offset):
		# TODO: Make this pay attention to offset
		node = self._find(path)
		if node is not None and isinstance(node, PownceFS.Base):
			if node.time + API_TTL < time.time():
				node.fetch()
			for n in node.children:
				yield fuse.Direntry(n)

	def read(self, path, length, offset):
		node = self._find(path)
		logging.debug('reading')
		if node is not None and isinstance(node, PownceFS.File):
			logging.debug('is a file')
			if node.time + API_TTL < time.time():
				logging.debug('fetching')
				node.fetch()
			logging.debug('really reading')
			return node.read(length, offset)

	class Base(object):
		"""
		Class just for the root node of the filesystem
		"""

		def __init__(self, token):
			self.token = token
			self.inode = inode()
			self.time = 472545720
			self.dev = 409089L
			self.children = {}
			self.name = None

		def __str__(self):
			return str(self.name)

		def getattr(self):
			return os.stat_result((
				stat.S_IFDIR | 0555,
				long(self.inode),
				self.dev,
				2,
				os.getuid(),
				os.getgid(),
				4096L,
				int(self.time),
				int(self.time),
				int(self.time)
			))

		def put(self, thing):
			"""
			Add a child to this node
			"""
			if isinstance(thing, PownceFS.Base):
				if thing.name:
					self.children[thing.name] = thing

		def get(self, name):
			"""
			Get a child of this node
			"""
			if name in self.children:
				return self.children[name]
			else:
				return None

		def fetch(self):
			"""
			Fetch the user's friend list
			""" 
			# TODO: Follow extra pages
			try:
				rsp = api.api(self.token, 'auth/verify')
				username = rsp['auth']['username']
				self.put(PownceFS.User(self.token, username))
				rsp = api.api(self.token, 'users/%s/friends' % username,
					{'limit': 100})
				users = rsp['friends']['users']
				for u in users:
					self.put(PownceFS.User(self.token, u['username']))
				self.time = time.time()
			except:
				pass

	class User(Base):
		"""
		Class to represent a Pownce user
		"""

		def __init__(self, token, name):
			PownceFS.Base.__init__(self, token)
			self.name = name

		def fetch(self):
			"""
			Fetch this friend's files
			"""
			# TODO: Follow extra pages
			try:
				rsp = api.api(self.token, 'note_lists/%s' % self.name,
					{'type': 'files', 'filter': 'sent', 'limit': 100})
				notes = rsp['notes']
				for n in notes:
					self.put(PownceFS.File(self.token, n['file']['name'],
						n['file']['aws_url'], n['file']['content_length']))
				self.time = time.time()
			except:
				pass

	class File(Base):
		"""
		Class to represent a file on Pownce
		"""

		def __init__(self, token, name, url, size):
			PownceFS.Base.__init__(self, token)
			self.children = None
			self.name = name
			self.url = url
			self.size = size

		def getattr(self):
			return os.stat_result((
				stat.S_IFREG | 0444,
				self.inode,
				self.dev,
				1,
				os.getuid(),
				os.getgid(),
				long(self.size),
				int(self.time),
				int(self.time),
				int(self.time)
			))

		def read(self, length, offset):
			try:
				f = open('%s/.powncefs/%d' % (os.path.expanduser('~'),
					self.inode), 'r')
				f.seek(offset)
				return f.read(length)
			except:
				return None

		def put(self, thing):
			return

		def get(self, name):
			return None

		def fetch(self):
			try:
				logging.debug(self.url)
				response = urllib2.urlopen(urllib2.Request(self.url))
				f = open('%s/.powncefs/%d' % (os.path.expanduser('~'),
					self.inode), 'w')
				f.write(response.read())
				f.close()
				self.time = time.time()
			except:
				pass

	def main(self, *a, **kw):
		return Fuse.main(self, *a, **kw)

	# Functions in the API (and in the xmp.py sample) but for which
	# I have no use (yet)
	def readlink(self, path):
		logging.debug('[info] readlink, path: %s' % path)
	def unlink(self, path):
		logging.debug('[info] unlink, path: %s' % path)
	def rmdir(self, path):
		logging.debug('[info] rmdir, path: %s' % path)
	def symlink(self, path, path1):
		logging.debug('[info] symlink, path: %s, path1: %s' % (path, path1))
	def rename(self, path, path1):
		logging.debug('[info] rename, path: %s, path1: %s' % (path, path1))
	def link(self, path, path1):
		logging.debug('[info] link, path: %s, path1: %s' % (path, path1))
	def chmod(self, path, mode):
		logging.debug('[info] chmod, path: %s, mode: %o' % (path, mode))
	def chown(self, path, user, group):
		logging.debug('[info] chown, path: %s, user: %s, group: %s' %
			(path, user, group))
	def truncate(self, path, length):
		logging.debug('[info] truncate, path: %s, length: %d' % (path, length))
	def mknod(self, path, mode, dev):
		logging.debug('[info] mknod, path: %s, mode: %o, dev: %s' %
			(path, mode, dev))
	def mkdir(self, path, mode):
		logging.debug('[info] mkdir, path: %s, mode: %o' % (path, mode))
	def utime(self, path, times):
		logging.debug('[info] utime, path: %s, times: %s' % (path, times))
	def statfs(self):
		logging.debug('[info] statfs - what the hell is this?')

def main():
	try:
		os.mkdir('%s/.powncefs' % os.path.expanduser('~'), 0700)
	except:
		pass
	logging.basicConfig(
		level = logging.DEBUG,
		format = '%(message)s',
		filename = '%s/.powncefs/log' % os.path.expanduser('~'),
		filemode = 'w'
	)
	fs = PownceFS()
	fs.parse(values = fs, errex = 1)
	fs.main()

if '__main__' == __name__:
	main()
