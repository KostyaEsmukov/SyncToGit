import os
import sys
import binascii
import logging
from socket import error as socketerror
from time import sleep
import urlparse

import regex  # \p{L}
import git

import EvernoteNoteParser
from Git import gitRepo


_EVERNOTE_SDK_URL = 'https://github.com/evernote/evernote-sdk-python.git'
_RETRIES = 10
_MAXLEN_TITLE_FILENAME = 30


# required API permissions:
# Read existing notebooks
# Read existing notes


def _init_update_sdk_repo(sdk_dir):
	if not os.path.isdir(sdk_dir):
		os.makedirs(sdk_dir)

	try:
		r = gitRepo(sdk_dir)
		r.git.reset('--hard')
		logging.info("Updating Evernote SDK...")
		r.remotes.origin.pull()
	except Exception, e:
		if len(os.listdir(sdk_dir)) > 0:
			raise Exception("SDK is corrupted: %s. Try to remove %s folder." % (e, sdk_dir))
		else:
			logging.info("Downloading Evernote SDK...")
			git.Repo.clone_from(_EVERNOTE_SDK_URL, sdk_dir)


_EvernoteClient = None
_Edam = None
_Constants = None
_Errors = None


def _get_EvernoteClient(sdk_dir):
	global _EvernoteClient, _Edam, _Constants, _Errors

	d = os.path.join(sdk_dir, "lib")
	d = os.path.abspath(d)

	if d not in sys.path:
		sys.path.append(d)

	from evernote.api.client import EvernoteClient
	import evernote.edam as Edam
	# import evernote.edam.userstore.constants as UserStoreConstants
	# import evernote.edam.type.ttypes as Types

	import evernote.edam.limits.constants as Constants
	import evernote.edam.error.constants as Errors

	_EvernoteClient = EvernoteClient
	_Edam = Edam
	_Constants = Constants
	_Errors = Errors


def _normalize_filename(fn):
	ec = "_"
	fn = fn.replace(ec, ec * 2)  # escape all escape chars
	if fn.strip() is '':
		fn = ec + fn + ec

	# https://msdn.microsoft.com/en-us/library/aa365247.aspx
	l = ["CON", "COM[0-9]", "LPT[0-9]", "PRN", "AUX", "NUL"]  # special msdos devices
	for s in l:
		if regex.match("^" + s, fn, regex.IGNORECASE):
			fn = ec + fn
			break

	p = regex.compile('[^\p{L}0-9\-_\. \[\]\(\)]', regex.UNICODE)

	fn = p.sub(lambda m: ec + ("%04x" % ord(m.group(0))), fn)

	return fn


class EvernoteTokenExpired(Exception):
	pass


def _IORetry(f):
	def c(*p, **k):
		ee = None
		for i in range(_RETRIES):
			try:
				return f(*p, **k)
			except (socketerror, EOFError) as e:
				logging.warning("IO failure: %d/%d: %s" % (i + 1, _RETRIES, repr(e)))
				ee = e
			except _Errors.EDAMSystemException as e:
				if e.errorCode == _Errors.EDAMErrorCode.RATE_LIMIT_REACHED:
					s = e.rateLimitDuration + 1
					logging.warning("Rate limit reached. Waiting %d seconds..." % s)
					sleep(s)
					ee = e
				else:
					raise
			except _Errors.EDAMUserException as e:
				if e.errorCode == _Errors.EDAMErrorCode.AUTH_EXPIRED or e.errorCode == _Errors.EDAMErrorCode.BAD_DATA_FORMAT:
					logging.debug(repr(e))
					raise EvernoteTokenExpired()
				else:
					raise

		raise ee

	return c


class EvernoteAuthException(Exception):
	pass


class Evernote:
	def __init__(self, sdk_dir, sandbox=True):
		_init_update_sdk_repo(sdk_dir)

		self.sandbox = sandbox
		_get_EvernoteClient(sdk_dir)
		self.client = None

	@_IORetry
	def retrieve_token(self, consumer_key, consumer_secret, callback_url):
		try:
			client = _EvernoteClient(
				consumer_key=consumer_key,
				consumer_secret=consumer_secret,
				sandbox=self.sandbox
			)

			request_token = client.get_request_token(callback_url)

			print "Open this link in your browser: "
			print client.get_authorize_url(request_token)
			print "After giving access you will be redirected to non-existing page. It's OK."
			url = raw_input("Paste the URL of that page here: ")

			oauth_verifier = urlparse.parse_qs(urlparse.urlsplit(url).query)['oauth_verifier'][0]

			return client.get_access_token(
				request_token['oauth_token'],
				request_token['oauth_token_secret'],
				oauth_verifier
			)
		except Exception as e:
			raise EvernoteAuthException(e)

	@_IORetry
	def auth(self, access_token):
		self.client = _EvernoteClient(token=access_token, sandbox=self.sandbox)

	@_IORetry
	def _get_notebooks(self):
		note_store = self.client.get_note_store()
		notebooks = note_store.listNotebooks()

		res = {}

		for n in notebooks:
			res[n.guid] = {
				'name': n.name,
				'updateSequenceNum': n.updateSequenceNum,
				'stack': n.stack if n.stack is not None else None
			}

		return res

	@_IORetry
	def _get_all_notes_metadata(self):
		note_store = self.client.get_note_store()

		noteFilter = _Edam.notestore.NoteStore.NoteFilter()
		noteFilter.ascending = False

		spec = _Edam.notestore.NoteStore.NotesMetadataResultSpec()
		spec.includeTitle = True
		spec.includeUpdateSequenceNum = True
		spec.includeNotebookGuid = True
		spec.includeTagGuids = True
		spec.includeCreated = True
		spec.includeUpdated = True
		spec.includeDeleted = True

		metadata = note_store.findNotesMetadata(noteFilter, 0, _Constants.EDAM_USER_NOTES_MAX, spec)

		res = {}

		for n in metadata.notes:
			res[n.guid] = {
				'title': n.title,
				'notebookGuid': n.notebookGuid,
				'updateSequenceNum': n.updateSequenceNum,
				'tagGuids': n.tagGuids,
				'updated': n.updated,
				'created': n.created,
				'deleted': n.deleted
			}

		return res, self._get_notebooks()

	def _process_metadata(self, metadata):
		res = {}

		for guid in metadata[0]:
			n = metadata[0][guid]
			nb = metadata[1][n['notebookGuid']]

			st = ([nb['stack']] if nb['stack'] else []) + [nb['name']]
			res[guid] = {
				'dir': list(map(lambda s: _normalize_filename(s.decode("utf8")), st)),
				'file': _normalize_filename(n['title'].decode("utf8")[0:_MAXLEN_TITLE_FILENAME] + "." + guid.decode("utf8")) + ".html",
				'name': map(lambda s: s.decode("utf8"), st + [n['title']]),
				'updateSequenceNum': n['updateSequenceNum']
			}

		return res

	def get_actual_metadata(self):
		return self._process_metadata(self._get_all_notes_metadata())

	@_IORetry
	def get_note(self, guid, resources_base):
		note_store = self.client.get_note_store()

		note = note_store.getNote(guid, True, True, False, False)

		note_parsed = EvernoteNoteParser.parse(resources_base, note.content, note.title.decode("utf8"))

		resources = {}
		if note.resources:
			for r in note.resources:
				chash = binascii.hexlify(r.data.bodyHash)
				resources[chash] = {
					'body': r.data.body,
					'mime': r.mime,
					'filename': ''.join([chash, '.', r.mime.split('/', 2)[1]]).decode("utf8")
				}

		return {
			'title': note.title,
			'updateSequenceNum': note.updateSequenceNum,
			'guid': note.guid,
			'created': note.created,
			'updated': note.updated,
			'html': note_parsed,
			'resources': resources
		}
