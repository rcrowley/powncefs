#!/usr/bin/python

"""
Pownce API Client for PownceFS
Richard Crowley
2008-03-19

Based almost completely on Leah's pownce_oauth_test.py from:
http://groups.google.com/group/pownceapi/browse_thread/thread/8cdf67c66b65fe58

http://svn.rcrowley.org/svn/powncefs/
$Id: api.py 3 2008-03-22 19:00:09Z rcrowley $

This work is licensed under the Creative Commons Attribution-Share Alike
3.0 Unported License. To view a copy of this license, visit
http://creativecommons.org/licenses/by-sa/3.0/ or send a letter to
Creative Commons, 171 Second Street, Suite 300, San Francisco,
California, 94105, USA.
"""

import urllib, urllib2, httplib, time
import oauth.oauth as oauth

import json

APP_KEY = 'uhg04637y1ken09880z4j9a96kfdd4l5'
APP_SECRET = '1nfdxzor4v725a379oa090207k57384x'

BASE_URL = 'http://api.pownce.com'
REQUEST_TOKEN_URL = '%s/oauth/request_token' % BASE_URL
ACCESS_TOKEN_URL = '%s/oauth/access_token' % BASE_URL
AUTHORIZATION_URL = '%s/oauth/authorize' % BASE_URL

def api(token, method, params={}):
	client = SimpleOAuthClient(
		REQUEST_TOKEN_URL, ACCESS_TOKEN_URL, AUTHORIZATION_URL)
	consumer = oauth.OAuthConsumer(APP_KEY, APP_SECRET)
	signature_method_hmac_sha1 = oauth.OAuthSignatureMethod_HMAC_SHA1()

	url = '%s/2.0/%s.json' % (BASE_URL, method)
	oauth_request = oauth.OAuthRequest.from_consumer_and_token(
		consumer, token=token, http_url=url, parameters=params)
	oauth_request.sign_request(signature_method_hmac_sha1, consumer, token)
	response = client.access_resource(oauth_request)
	return json.read(response.read())

def auth(verbose=False):
	client = SimpleOAuthClient(
		REQUEST_TOKEN_URL, ACCESS_TOKEN_URL, AUTHORIZATION_URL)
	consumer = oauth.OAuthConsumer(APP_KEY, APP_SECRET)
	signature_method_hmac_sha1 = oauth.OAuthSignatureMethod_HMAC_SHA1()

	if verbose:
		response = urllib2.urlopen(BASE_URL)
		print response.read()

	if verbose:
		print 'Endpoint: Request Token (OAuth)'
	oauth_request = oauth.OAuthRequest.from_consumer_and_token(
		consumer, http_url=client.request_token_url)
	oauth_request.sign_request(signature_method_hmac_sha1, consumer, None)
	if verbose:
		print 'Parameters:'
		print str(oauth_request.parameters)
	response = client.fetch_request_token(oauth_request)
	if verbose:
		print 'Response:'
	token = None
	if response.__class__ is oauth.OAuthToken:
		token = response
		if verbose:
			print 'request token key: %s' % str(token.key)
			print 'request token secret: %s' % str(token.secret)
	else:
		if verbose:
			print response.read()
		return

	if verbose:
		print 'Endpoint: Authorize (OAuth)'
	oauth_request = oauth.OAuthRequest.from_token_and_callback(
		token=token, http_url=client.authorization_url)
	if verbose:
		print 'Parameters:'
		print str(oauth_request.parameters)
	response = client.get_authorization_url(oauth_request)
	print 'Visit this URL in your browser and login.'
	print response
	raw_input('Afterwards, come back here and press ENTER.')

	if verbose:
		print 'Endpoint: Access Token (OAuth)'
	oauth_request = oauth.OAuthRequest.from_consumer_and_token(
		consumer, token=token, http_url=client.access_token_url)
	oauth_request.sign_request(signature_method_hmac_sha1, consumer, token)
	if verbose:
		print 'Parameters:'
		print str(oauth_request.parameters)
	response = client.fetch_access_token(oauth_request)
	if verbose:
		print 'Response:'
	token = None
	if response.__class__ is oauth.OAuthToken:
		token = response
		if verbose:
			print 'access token key: %s' % str(token.key)
			print 'access token secret: %s' % str(token.secret)
		return token
	else:
		print response.read()
		return

def test(token):
	client = SimpleOAuthClient(
		REQUEST_TOKEN_URL, ACCESS_TOKEN_URL, AUTHORIZATION_URL)
	consumer = oauth.OAuthConsumer(APP_KEY, APP_SECRET)
	signature_method_hmac_sha1 = oauth.OAuthSignatureMethod_HMAC_SHA1()

	print 'Endpoint: Verify Auth (OAuth)'
	url = '%s/auth/verify.xml' % BASE_URL
	oauth_request = oauth.OAuthRequest.from_consumer_and_token(
		consumer, token=token, http_url=url)
	oauth_request.set_parameter('app_key', APP_KEY)
	oauth_request.sign_request(signature_method_hmac_sha1, consumer, token)
	print 'Parameters:'
	print str(oauth_request.parameters)
	response = client.access_resource(oauth_request)
	print 'Response:'
	print response.read()

class SimpleOAuthClient(oauth.OAuthClient):

	def __init__(self, request_token_url='', access_token_url='',
		authorization_url=''):
		self.request_token_url = request_token_url
		self.access_token_url = access_token_url
		self.authorization_url = authorization_url

	def fetch_request_token(self, oauth_request):
		response = self._open_url(oauth_request.to_url(),
			oauth_header=oauth_request.to_header())
		try:
			return oauth.OAuthToken.from_string(response.read())
		except:
			return response

	def fetch_access_token(self, oauth_request):
		response = self._open_url(oauth_request.to_url(),
			oauth_header=oauth_request.to_header())
		try:
			return oauth.OAuthToken.from_string(response.read())
		except:
			return response

	def get_authorization_url(self, oauth_request):
		return oauth_request.to_url()

	def access_resource(self, oauth_request):
		if 'GET' == oauth_request.http_method:
			response = self._open_url(oauth_request.to_url())
		elif 'POST' == oauth_request.http_method:
			response = self._open_url(oauth_request.http_url,
				post_params=oauth_request.parameters)
		else:
			response = self._open_url(oauth_request.http_url,
				oauth_header=oauth_request.to_header())
		return response

	def _open_url(self, url, oauth_header=None, post_params=None):
		if post_params:
			post_data = urllib.urlencode(post_params)
			req = urllib2.Request(url, data=post_data)
		else:
			req = urllib2.Request(url)
		if oauth_header:
			req.add_header('Authorization', oauth_header['Authorization'])
		try:
			response = urllib2.urlopen(req)
			return response
		except Exception, ex:
			pass

if '__main__' == __name__:
	token = auth(True)
	test(token)
