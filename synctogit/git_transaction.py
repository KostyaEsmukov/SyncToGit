from __future__ import absolute_import

import os
import errno
from copy import copy
from datetime import datetime
import logging
import shutil
import re


def _mkdir_p(d):
    # `mkdir -p $d`

    try:
        os.makedirs(u'' + d)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(d):
            pass
        else:
            raise


def _rmfile(fp):
    try:
        os.remove(u'' + fp)
    except IOError as e:
        logging.warn("Unable to delete %s file: %s" % (fp, repr(e)))


def _write_to_file(fn, body):
    with open(u'' + fn, 'wb') as f:
        f.write(body)


class GitSimultaneousTransaction(Exception):
    pass


class GitTransaction:
    def __init__(self, git, repo_dir, branch, push):
        self.repo_dir = unicode(repo_dir)
        self.branch = branch
        self.push = push

        self.git = git

    def _remove_dirs_until_not_empty(self, d):
        d = copy(d)
        try:
            while d:
                os.rmdir(self._abspath(d))
                d.pop()
        except:
            pass

    def _abspath(self, l):
        r = unicode(os.path.join(*([self.repo_dir] + l)))
        if not r.startswith(self.repo_dir):
            raise Exception("Foreign path has been chosen!")
        return r

    def _delete_non_existing_resources(self, metadata):
        try:
            root, dirs, _ = os.walk(self._abspath(["Resources"])).next()

            for d in dirs:
                if d not in metadata:
                    logging.warning("Resources for non-existing note %s are going to be removed." % d)
                    shutil.rmtree(os.path.join(root, d))
        except StopIteration:
            return

    def _scan_get_notes_metadata(self):

        def _rem(f, d=None):
            logging.warning("Corrupted note is going to be removed: %s" % f)
            _rmfile(f)
            if d:
                self._remove_dirs_until_not_empty(["Notes"] + d)

        metadata = {}
        corrupted = {}

        for root, dirs, files in os.walk(self._abspath(["Notes"])):
            for fn in files:
                _, ext = os.path.splitext(fn)

                if ext != ".html":
                    continue

                cur = {
                    'file': fn,
                    'dir': root.split(os.path.sep),
                    'fp': os.path.join(root, fn)
                }

                while cur['dir'] and cur['dir'][0] != "Notes":
                    cur['dir'] = cur['dir'][1:]

                if not (2 <= len(cur['dir']) <= 3):
                    _rem(cur['fp'])
                    continue

                cur['dir'] = cur['dir'][1:]

                try:
                    # guid, updateSequenceNum
                    with open(cur['fp'], "r") as f:
                        while len(cur) != 5:
                            l = f.readline()

                            if l is '':
                                break

                            g = re.search('^<!--[-]+-->$', l)
                            if g is not None:
                                break

                            g = re.search('^<!-- ([^:]+): (.+) -->$', l)
                            if g is not None:
                                k = g.group(1)
                                v = g.group(2)

                                if k in ["guid"]:
                                    cur[k] = v
                                if k in ["updateSequenceNum"]:
                                    cur[k] = int(v)
                except Exception as e:
                    logging.warn("Unable to parse the note. Discarding it. %s", repr(e))

                if len(cur) != 5:
                    _rem(cur['fp'], cur['dir'])
                    continue

                if cur['guid'] in metadata:
                    _rem(cur['fp'], cur['dir'])
                    _rem(metadata[cur['guid']]['fp'], metadata[cur['guid']]['dir'])
                    del metadata[cur['guid']]
                    corrupted[cur['guid']] = True
                elif cur['guid'] in corrupted:
                    _rem(cur['fp'], cur['dir'])
                else:
                    metadata[cur['guid']] = cur

        self._delete_non_existing_resources(metadata)

        return metadata

    def _stash(self):
        if self.git.is_dirty(untracked_files=True):
            logging.warning("Git repo is dirty. Working copy is going to be be stashed.")

            self.git.git.stash()

    def _check_repo_state(self):
        self._stash()

        if self.branch != self.git.active_branch.name:
            logging.info("Switching branch")
            self.git.git.checkout("-b", self.branch)

    def _commit_changes(self):
        self.git.git.add(["-A",
                          "."])  # there are problems with charset under windows when using python version: self.git.index.add("*")
        self.git.index.commit("Sync at " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def _lockfile_location(self):
        return self._abspath([".synctogit.lockfile"])

    def _lockfile_create(self):
        with open(self._lockfile_location(), "wb") as f:
            f.write("1")

    def _lockfile_exists(self):
        return os.path.isfile(self._lockfile_location())

    def _lockfile_remove(self):
        _rmfile(self._lockfile_location())

    def __enter__(self):
        if self._lockfile_exists():
            raise GitSimultaneousTransaction("Lockfile exists. Another copy of program is probably running. "
                                             "Remove this file if you are sure that this is a mistake: %s" % self._lockfile_location())

        self._check_repo_state()
        self._lockfile_create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lockfile_remove()

        if exc_type is not None:
            logging.warning("git transaction failed: %s(%s)" % (repr(exc_type), exc_val))
            self._stash()
        else:
            if self.git.is_dirty(untracked_files=True):
                self._commit_changes()

            if self.push:
                try:
                    self.git.remotes.origin.push()
                except Exception as e:
                    logging.warning("Failed to git push: %s", repr(e))

    def calculate_changes(self, evernoteMetadata, force_update):
        new = evernoteMetadata
        old = self._scan_get_notes_metadata()

        res = {
            'new': {},
            'update': {},
            'delete': {},
            'result': []
        }

        oldguids = copy(old)
        for guid in new:
            res['result'].append([new[guid]['dir'] + [new[guid]['file']], new[guid]['name']])
            if guid not in old:
                res['new'][guid] = new[guid]
            else:
                if cmp(new[guid]['file'], old[guid]['file']) != 0:
                    res['delete'][guid] = old[guid]
                    res['new'][guid] = new[guid]
                elif force_update or new[guid]['updateSequenceNum'] != old[guid]['updateSequenceNum']:
                    res['update'][guid] = new[guid]

                oldguids.pop(guid, 0)

        for guid in oldguids:
            res['delete'][guid] = oldguids[guid]

        return res

    def delete_files(self, files):
        for guid in files:
            fp = self._abspath(["Notes"] + files[guid]['dir'] + [files[guid]['file']])
            _rmfile(fp)

            self._remove_dirs_until_not_empty(["Notes"] + files[guid]['dir'])

    def get_relative_resources_url(self, noteguid, metadata):
        # utf8 encoded
        return '/'.join(([".."] * (len(metadata['dir']) + 1)) + ["Resources", noteguid, ""]).encode("utf8")

    # return os.path.join(*(([".."] * (len(metadata['dir']) + 1)) + ["Resources", noteguid, ""]))

    def save_note(self, note, metadata):
        _mkdir_p(self._abspath(["Notes"] + metadata['dir']))

        header = []
        header += ["<!doctype html>"]
        header += ["<!-- PLEASE DO NOT EDIT THIS FILE -->"]
        header += ["<!-- All changes you've done here will be stashed on next sync -->"]
        header += ["<!--+++++++++++++-->"]
        for k in ["guid", "updateSequenceNum", "title", "created", "updated"]:
            v = note[k]
            if k in ["created", "updated"]:
                v = datetime.fromtimestamp(v / 1000).strftime('%Y-%m-%d %H:%M:%S')

            header += ["<!-- %s: %s -->" % (k, v)]

        header += ["<!----------------->"]
        header += [""]

        body = '\n'.join(header) + note['html']

        f = self._abspath(["Notes"] + metadata['dir'] + [metadata['file']])
        _write_to_file(f, body)

        p = ["Resources"] + [note['guid']]
        try:
            shutil.rmtree(self._abspath(p))
        except:
            pass

        if len(note['resources']) > 0:
            _mkdir_p(self._abspath(p))

            for guid in note['resources']:
                m = note['resources'][guid]

                f = self._abspath(p + [m['filename']])
                _write_to_file(f, m['body'])
