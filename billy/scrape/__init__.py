import time
import logging
import datetime
import json
from collections import defaultdict

from billy.scrape.validator import DatetimeValidator

from billy.conf import settings

import scrapelib


class ScrapeError(Exception):
    """
    Base class for scrape errors.
    """
    def __init__(self, msg, orig_exception=None):
        self.msg = msg
        self.orig_exception = orig_exception

    def __str__(self):
        if self.orig_exception:
            return '%s\nOriginal Exception: %s' % (self.msg,
                                        self.orig_exception)
        else:
            return self.msg


class NoDataForPeriod(ScrapeError):
    """
    Exception to be raised when no data exists for a given period
    """
    def __init__(self, period):
        self.period = period

    def __str__(self):
        return 'No data exists for %s' % self.period


class JSONDateEncoder(json.JSONEncoder):
    """
    JSONEncoder that encodes datetime objects as Unix timestamps.
    """
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return time.mktime(obj.utctimetuple())
        elif isinstance(obj, datetime.date):
            return time.mktime(obj.timetuple())

        return json.JSONEncoder.default(self, obj)

_scraper_registry = defaultdict(dict)


class ScraperMeta(type):
    """ register derived scrapers in a central registry """

    def __new__(meta, classname, bases, classdict):
        cls = type.__new__(meta, classname, bases, classdict)

        state = getattr(cls, 'state', None)
        scraper_type = getattr(cls, 'scraper_type', None)

        if state and scraper_type:
            _scraper_registry[state][scraper_type] = cls

        return cls


class Scraper(scrapelib.Scraper):
    """ Base class for all Scrapers

    Provides several useful methods for retrieving URLs and checking
    arguments against metadata.
    """

    __metaclass__ = ScraperMeta

    def __init__(self, metadata, no_cache=False, output_dir=None,
                 strict_validation=None, **kwargs):
        """
        Create a new Scraper instance.

        :param metadata: metadata for this state
        :param no_cache: if True, will ignore any cached downloads
        :param output_dir: the data directory to use
        :param strict_validation: exit immediately if validation fails
        """

        # configure underlying scrapelib object
        if no_cache:
            kwargs['cache_dir'] = None
        elif 'cache_dir' not in kwargs:
            kwargs['cache_dir'] = settings.BILLY_CACHE_DIR

        if 'error_dir' not in kwargs:
            kwargs['error_dir'] = settings.BILLY_ERROR_DIR

        if 'timeout' not in kwargs:
            kwargs['timeout'] = settings.SCRAPELIB_TIMEOUT

        if 'requests_per_minute' not in kwargs:
            kwargs['requests_per_minute'] = None

        if 'retry_attempts' not in kwargs:
            kwargs['retry_attempts'] = settings.SCRAPELIB_RETRY_ATTEMPTS

        if 'retry_wait_seconds' not in kwargs:
            kwargs['retry_wait_seconds'] = \
                    settings.SCRAPELIB_RETRY_WAIT_SECONDS

        super(Scraper, self).__init__(**kwargs)

        if not hasattr(self, 'state'):
            raise Exception('Scrapers must have a state attribute')

        self.metadata = metadata
        self.output_dir = output_dir

        # validation
        self.strict_validation = strict_validation
        self.validator = DatetimeValidator()

        self.follow_robots = False

        # logging convenience methods
        self.logger = logging.getLogger("billy")
        self.log = self.logger.info
        self.debug = self.logger.debug
        self.warning = self.logger.warning

    def validate_object(self, obj):
        try:
            obj.validate()
        except ValueError as ve:
            self.warning(str(ve))
            if self.strict_validation:
                raise ve

    def validate_session(self, session):
        """ Check that a session is present in the metadata dictionary.

        raises :exc:`~billy.scrape.NoDataForPeriod` if session is invalid

        :param session:  string representing session to check
        """
        for t in self.metadata['terms']:
            if session in t['sessions']:
                return True
        raise NoDataForPeriod(session)

    def validate_term(self, term, latest_only=False):
        """ Check that a term is present in the metadata dictionary.

        raises :exc:`~billy.scrape.NoDataForPeriod` if term is invalid

        :param term:        string representing term to check
        :param latest_only: if True, will raise exception if term is not
                            the current term (default: False)
        """

        if latest_only:
            if term == self.metadata['terms'][-1]['name']:
                return True
            else:
                raise NoDataForPeriod(term)

        for t in self.metadata['terms']:
            if term == t['name']:
                return True
        raise NoDataForPeriod(term)


class SourcedObject(dict):
    """ Base object used for data storage.

    Base class for :class:`~billy.scrape.bills.Bill`,
    :class:`~billy.scrape.legislators.Legislator`,
    :class:`~billy.scrape.votes.Vote`,
    and :class:`~billy.scrape.committees.Committee`.

    SourcedObjects work like a dictionary.  It is possible
    to add extra data beyond the required fields by assigning to the
    `SourcedObject` instance like a dictionary.
    """

    validator = DatetimeValidator()
    schema = None

    def __init__(self, _type, **kwargs):
        super(SourcedObject, self).__init__()
        self['_type'] = _type
        self['sources'] = []
        self.update(kwargs)

    def add_source(self, url, retrieved=None, **kwargs):
        """
        Add a source URL from which data related to this object was scraped.

        :param url: the location of the source
        """
        retrieved = retrieved or datetime.datetime.utcnow()
        self['sources'].append(dict(url=url, retrieved=retrieved, **kwargs))

    def validate(self):
        if self.schema:
            self.validator.validate(self, self.schema)


def get_scraper(mod_path, state, scraper_type):
    """ import a scraper from the scraper registry """

    # act of importing puts it into the registry
    try:
        mod_path = '%s.%s' % (mod_path, scraper_type)
        __import__(mod_path)
    except ImportError as e:
        raise ScrapeError("could not import %s" % mod_path, e)

    # now pull the class out of the registry
    try:
        ScraperClass = _scraper_registry[state][scraper_type]
    except KeyError as e:
        raise ScrapeError("no %s %s scraper found" %
                           (state, scraper_type))
    return ScraperClass
