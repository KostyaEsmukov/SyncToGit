import regex

# special msdos devices
# https://msdn.microsoft.com/en-us/library/aa365247.aspx
_MSDOS_FILENAME_PATTERN = regex.compile(r'^(%s)' % '|'.join(
    ["CON", "COM[0-9]", "LPT[0-9]", "PRN", "AUX", "NUL"]
), flags=regex.IGNORECASE)

_STRIP_CHARS_FILENAME_PATTERN = regex.compile(
    r'[^\p{L}0-9\-_\. \[\]\(\)]',
    flags=regex.UNICODE,
)


def is_msdos_filename(filename: str):
    return _MSDOS_FILENAME_PATTERN.match(filename) is not None


def normalize_filename(filename: str) -> str:
    escape_char = "_"
    # escape all escape chars
    filename = filename.replace(escape_char, escape_char * 2)
    if not filename.strip():
        filename = "%(escape_char)s%(filename)s%(escape_char)s" % locals()

    if not filename:
        return ""

    if is_msdos_filename(filename) or filename[0] == '.':
        filename = "%(escape_char)s%(filename)s" % locals()

    filename = _STRIP_CHARS_FILENAME_PATTERN.sub(
        lambda m: escape_char + ("%04x" % ord(m.group(0))),
        filename,
    )

    return filename
