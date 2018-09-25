import errno
import logging
import os
import re
import shutil
from copy import copy
from datetime import datetime
from typing import Mapping

import git

from synctogit.evernote.models import Note, NoteGuid, NoteMetadata

logger = logging.getLogger(__name__)


def _mkdir_p(d):
    # `mkdir -p $d`

    try:
        os.makedirs('' + d)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(d):
            pass
        else:
            raise


def _rmfile(fp):
    try:
        os.remove('' + fp)
    except IOError as e:
        logger.warn("Unable to delete %s file: %s" % (fp, repr(e)))


def _write_to_file(fn: str, body: str):
    with open(fn, 'wb') as f:
        f.write(body)


class GitSimultaneousTransaction(Exception):
    pass


class GitTransaction:
    # Must be thread-safe.

    def __init__(self, repo: git.Repo, push: bool) -> None:
        self.repo_dir = repo.working_tree_dir
        self.push = push

        self.git = repo

    def _remove_dirs_until_not_empty(self, d):
        d = copy(d)
        try:
            while d:
                os.rmdir(self._abspath(d))
                d.pop()
        except Exception:
            pass

    def _abspath(self, l):
        r = str(os.path.join(*([self.repo_dir] + l)))
        if not r.startswith(self.repo_dir):
            raise Exception("Foreign path has been chosen!")
        return r

    def _delete_non_existing_resources(self, metadata):
        try:
            root, dirs, _ = next(os.walk(self._abspath(["Resources"])))

            for d in dirs:
                if d not in metadata:
                    logger.warning(
                        "Resources for non-existing note %s are going to be removed." % d
                    )
                    shutil.rmtree(os.path.join(root, d))
        except StopIteration:
            return

    def _scan_get_notes_metadata(self) -> Mapping[NoteGuid, NoteMetadata]:
        def _rem(f, d=None):
            logger.warning("Corrupted note is going to be removed: %s" % f)
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
                    'fp': os.path.join(root, fn),
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
                            line = f.readline()

                            if line is '':
                                break

                            g = re.search('^<!--[-]+-->$', line)
                            if g is not None:
                                break

                            g = re.search('^<!-- ([^:]+): (.+) -->$', line)
                            if g is not None:
                                k = g.group(1)
                                v = g.group(2)

                                if k in ["guid"]:
                                    cur[k] = v
                                if k in ["updateSequenceNum"]:
                                    cur[k] = int(v)
                except Exception as e:
                    logger.warn("Unable to parse the note. Discarding it. %s", repr(e))

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

        return {
            guid: NoteMetadata(
                dir=note['dir'],
                name=None,  # XXX
                update_sequence_num=note['updateSequenceNum'],
                file=note['file'],
            )
            for guid, note in metadata.items()
        }
        return metadata

    def _stash(self):
        if self.git.is_dirty(untracked_files=True):
            logger.warning(
                "Git repo is dirty. Working copy is going to be be stashed."
            )

            self.git.git.stash()

    def _check_repo_state(self):
        self._stash()

    def _commit_changes(self):
        # there are problems with charset under windows when using
        # python version: self.git.index.add("*")
        self.git.git.add(["-A", "."])
        self.git.index.commit("Sync at " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def _lockfile_location(self):
        return self._abspath([".synctogit.lockfile"])

    def _lockfile_create(self):
        with open(self._lockfile_location(), "wb") as f:
            f.write(b"1")

    def _lockfile_exists(self):
        return os.path.isfile(self._lockfile_location())

    def _lockfile_remove(self):
        _rmfile(self._lockfile_location())

    def __enter__(self):
        if self._lockfile_exists():
            raise GitSimultaneousTransaction(
                "Lockfile exists. Another copy of program is probably running. "
                "Remove this file if you are sure that this is "
                "a mistake: %s" % self._lockfile_location()
            )

        self._check_repo_state()
        self._lockfile_create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._lockfile_remove()

        if exc_type is not None:
            logger.warning(
                "git transaction failed: %s(%s)" % (repr(exc_type), exc_val)
            )
            self._stash()
        else:
            if self.git.is_dirty(untracked_files=True):
                self._commit_changes()

            if self.push:
                try:
                    self.git.remotes.origin.push()
                except Exception as e:
                    logger.warning("Failed to git push: %s", repr(e))

    def calculate_changes(
        self,
        evernote_metadata: Mapping[NoteGuid, NoteMetadata],
        force_update: bool,
    ):
        new = evernote_metadata
        old = self._scan_get_notes_metadata()

        res = {
            'new': {},
            'update': {},
            'delete': {},
            'result': [],
        }

        oldguids = copy(old)
        for guid, note in new.items():
            res['result'].append(
                [note.dir + [note.file], note.name]
            )
            if guid not in old:
                res['new'][guid] = note
            else:
                if note.file != old[guid].file:
                    res['delete'][guid] = old[guid]
                    res['new'][guid] = note
                elif (
                    force_update
                    or note.update_sequence_num != old[guid].update_sequence_num
                ):
                    res['update'][guid] = note

                oldguids.pop(guid, 0)

        for guid in oldguids:
            res['delete'][guid] = oldguids[guid]

        return res

    def delete_files(self, files: Mapping[NoteGuid, NoteMetadata]):
        for note in files.values():
            fp = self._abspath(["Notes"] + note.dir + [note.file])
            _rmfile(fp)

            self._remove_dirs_until_not_empty(["Notes"] + note.dir)

    def get_relative_resources_url(self, noteguid: NoteGuid, metadata: NoteMetadata):
        # utf8 encoded
        return '/'.join(
            ([".."] * (len(metadata.dir) + 1)) + ["Resources", noteguid, ""]
        )

    # return os.path.join(*(([".."] * (len(metadata['dir']) + 1))
    # + ["Resources", noteguid, ""]))

    def save_note(self, note: Note, metadata: NoteMetadata):
        _mkdir_p(self._abspath(["Notes"] + metadata.dir))

        header = []
        header += ["<!doctype html>"]
        header += ["<!-- PLEASE DO NOT EDIT THIS FILE -->"]
        header += ["<!-- All changes you've done here will be stashed on next sync -->"]
        header += ["<!--+++++++++++++-->"]
        for k in ["guid", "updateSequenceNum", "title", "created", "updated"]:
            k_ = re.sub('([A-Z]+)', r'_\1', k).lower()
            v = getattr(note, k_)
            if k in ["created", "updated"]:
                v = v.strftime('%Y-%m-%d %H:%M:%S')

            header += ["<!-- %s: %s -->" % (k, v)]

        header += ["<!----------------->"]
        header += [""]

        body = '\n'.join(header).encode() + note.html  # type: bytes

        f = self._abspath(["Notes"] + metadata.dir + [metadata.file])
        _write_to_file(f, body)

        p = ["Resources"] + [note.guid]
        try:
            shutil.rmtree(self._abspath(p))
        except Exception:
            pass

        if note.resources:
            _mkdir_p(self._abspath(p))

            for m in note.resources.values():
                f = self._abspath(p + [m.filename])
                _write_to_file(f, m.body)
