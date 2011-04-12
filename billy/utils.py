import re
import urllib
import urlparse
import logging

from billy import db


# Adapted from NLTK's english stopwords
stop_words = [
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
    'you', 'your', 'yours', 'yourself', 'yourselves',
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
    'herself', 'it', 'its', 'itself', 'they',
    'them', 'their', 'theirs', 'themselves', 'what',
    'which',  'who', 'whom', 'this', 'that', 'these', 'those',
    'am', 'is', 'are', 'was', 'were', 'be', 'been',
    'being', 'have', 'has', 'had', 'having', 'do', 'does',
    'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or',
    'because', 'as', 'until', 'while', 'of', 'at', 'by',
    'for', 'with', 'about', 'against', 'between',
    'into', 'through', 'during', 'before', 'after',
    'above', 'below', 'to', 'from', 'up', 'down', 'in',
    'out', 'on', 'off', 'over', 'under', 'again', 'further',
    'then', 'once', 'here', 'there', 'when', 'where', 'why',
    'how', 'all', 'any', 'both', 'each', 'few', 'more',
    'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very',
    's', 't', 'can', 'will', 'just', 'don', 'should',
    'now', '']


def tokenize(str):
    return re.split(r"[\s.,!?'\"`()]+", str)


def keywordize(str):
    """
    Splits a string into words, removes common stopwords, stems and removes
    duplicates.
    """
    import jellyfish
    return set([jellyfish.porter_stem(word.lower().encode('ascii',
                                                          'ignore'))
                for word in tokenize(str)
                if (word.isalpha() or word.isdigit()) and
                word.lower() not in stop_words])


def memoize(fun):
    cache = {}
    def new_fun(*args):
        try:
            return cache[args]
        except KeyError:
            value = fun(*args)
            cache[args] = value
            return value
    return new_fun


@memoize
def metadata(state):
    """
    Grab the metadata for the given state (two-letter abbreviation).
    """
    return db.metadata.find_one({'_id': state.lower()})


def chamber_name(state, chamber):
    if chamber == 'joint':
        return 'Joint'

    return metadata(state)['%s_chamber_name' % chamber].split()[0]


def term_for_session(state, session):
    meta = metadata(state)

    for term in meta['terms']:
        if session in term['sessions']:
            return term['name']

    raise ValueError("no such session")


def urlescape(url):
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(url)
    path = urllib.quote(path, '/%')
    qs = urllib.quote_plus(qs, ':&=')
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


def extract_fields(d, fields, delimiter='|'):
    """ get values out of an object ``d`` for saving to a csv """
    rd = {}
    for f in fields:
        v = d.get(f, None)
        if isinstance(v, (str, unicode)):
            v = v.encode('utf8')
        elif isinstance(v, list):
            v = delimiter.join(v)
        rd[f] = v
    return rd


def configure_logging(verbosity_count=0, state=None):
    verbosity = {0: logging.WARNING, 1: logging.INFO}.get(verbosity_count,
                                                          logging.DEBUG)
    if state:
        format = "%(asctime)s %(name)s %(levelname)s " + state + " %(message)s"
    else:
        format = "%(asctime)s %(name)s %(levelname)s %(message)s"
    logging.basicConfig(level=verbosity, format=format, datefmt="%H:%M:%S")
