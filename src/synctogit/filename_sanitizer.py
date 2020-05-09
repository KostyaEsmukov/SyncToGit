import mimetypes

import regex

_escape_char = "_"
_max_filename_len = 250  # https://stackoverflow.com/q/1065993

# special msdos devices
# https://msdn.microsoft.com/en-us/library/aa365247.aspx
_MSDOS_FILENAME_PATTERN = regex.compile(
    r"^(%s)(?:[.]|$)" % "|".join(["CON", "COM[0-9]", "LPT[0-9]", "PRN", "AUX", "NUL"]),
    flags=regex.IGNORECASE,
)

_STRIP_CHARS_FILENAME_PATTERN = regex.compile(
    r"[^\p{L}0-9\-_\. \[\]\(\)]", flags=regex.UNICODE,
)
_STRIPPED_CHAR_PATTERN = regex.compile(
    r"(%(e)s*)((?:%(e)s[0-9a-f]{4})+)" % dict(e=_escape_char)
)


def is_msdos_filename(filename: str):
    return _MSDOS_FILENAME_PATTERN.match(filename) is not None


def normalize_filename(filename: str) -> str:
    if not filename:
        raise ValueError("File name cannot be empty")

    escape_char = _escape_char  # make it available in locals()

    def escape(m):
        b = m.group(0).encode("utf-16be")
        return "".join(
            "%s%s" % (escape_char, b[i : i + 2].hex()) for i in range(0, len(b), 2)
        )

    # escape all escape chars
    filename = filename.replace(escape_char, escape_char * 2)

    filename = regex.sub(r"(^\s|\s$)", escape, filename)

    if is_msdos_filename(filename) or filename[0] == ".":
        filename = "%(escape_char)s%(filename)s" % locals()

    filename = _STRIP_CHARS_FILENAME_PATTERN.sub(escape, filename)

    if len(filename) > _max_filename_len:
        raise ValueError(
            "Normalized filename length exceeds the limit of %s" % _max_filename_len
        )

    return filename


def denormalize_filename(filename: str) -> str:
    if not filename:
        raise ValueError("File name cannot be empty")

    escape_char = _escape_char  # make it available in locals()

    def sub(m):
        e = m.group(1)
        if len(e) % 2 == 1:
            return m.group(0)

        hex_bytes = m.group(2).replace("_", "")
        s = bytes.fromhex(hex_bytes).decode("utf-16be")
        return "%s%s" % (m.group(1), s)

    filename = _STRIPPED_CHAR_PATTERN.sub(sub, filename)

    filename = filename.replace(escape_char * 2, escape_char)

    if len(filename) > 1 and filename[0] == escape_char:
        if is_msdos_filename(filename[1:]) or filename[1] == ".":
            filename = filename[1:]

    return filename


def ext_from_mime_type(mime_type: str) -> str:
    hardcoded_mime_type_conversions = {
        # On macOS (at least) text/plain might resolve to `.c` or `.ksh`.
        "text/plain": "txt",
    }
    ext = hardcoded_mime_type_conversions.get(mime_type)
    if ext:
        return ext
    ext_list = mimetypes.guess_all_extensions(mime_type, strict=True)
    if ext_list:
        # There might be a handful of them. Sort them so the result
        # is more or less consistent.
        ext = sorted(ext_list)[0]
        return ext.lstrip(".")
    _, ext = mime_type.split("/", 2)
    return ext
