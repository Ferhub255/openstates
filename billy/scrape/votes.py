import os
import itertools
import json

from billy.scrape import Scraper, SourcedObject, JSONDateEncoder
from billy.scrape.utils import get_sessions


class VoteScraper(Scraper):
    scraper_type = 'votes'

    def __init__(self, *args, **kwargs):
        super(VoteScraper, self).__init__(*args, **kwargs)
        self.sequence = itertools.count()

    def scrape(self, chamber, session):
        """
        Grab all votes for a given chamber and session.  Must be overridden
        by subclasses.

        Should raise a :class:`NoDataForPeriod` exception if it is not
        possible to scrape votes for the provided session.
        """
        raise NotImplementedError('VoteScrapers must define a scrape method')

    def save_vote(self, vote):
        """
        Save a scraped :class:`~billy.scrape.votes.Vote` object.

        Should be called after all data for the given vote is collected.
        """
        filename = '%s_%s_%s_seq%s.json' % (vote['session'],
                                            vote['chamber'],
                                            vote['bill_id'],
                                            self.sequence.next())

        self.log("save_vote %s %s: %s '%s'" % (vote['session'],
                                               vote['chamber'],
                                               vote['bill_id'],
                                               vote['motion']))

        self.validate_object(vote)

        with open(os.path.join(self.output_dir, 'votes', filename), 'w') as f:
            json.dump(vote, f, cls=JSONDateEncoder)


class Vote(SourcedObject):
    standalone_schema = json.load(
        open(os.path.join(os.path.split(__file__)[0],
                          '../schemas/vote.json')))

    def __init__(self, chamber, date, motion, passed,
                 yes_count, no_count, other_count, type='other', **kwargs):
        """
        Create a new :obj:`Vote`.

        :param chamber: the chamber in which the vote was taken,
          'upper' or 'lower'
        :param date: the date/time when the vote was taken
        :param motion: a string representing the motion that was being voted on
        :param passed: did the vote pass, True or False
        :param yes_count: the number of 'yes' votes
        :param no_count: the number of 'no' votes
        :param other_count: the number of abstentions, 'present' votes,
          or anything else not covered by 'yes' or 'no'.
        :param type: vote type classification

        Any additional keyword arguments will be associated with this
        vote and stored in the database.

        Examples: ::

          Vote('upper', '', '12/7/08', 'Final passage',
               True, 30, 8, 3)
          Vote('lower', 'Finance Committee', '3/4/03 03:40:22',
               'Recommend passage', 12, 1, 0)
        """
        super(Vote, self).__init__('vote', **kwargs)
        self['chamber'] = chamber
        self['date'] = date
        self['motion'] = motion
        self['passed'] = passed
        self['yes_count'] = yes_count
        self['no_count'] = no_count
        self['other_count'] = other_count
        self['type'] = type
        self['yes_votes'] = []
        self['no_votes'] = []
        self['other_votes'] = []

    def yes(self, legislator):
        """
        Indicate that a legislator (given as a string of their name) voted
        'yes'.

        Examples: ::

           vote.yes('Smith')
           vote.yes('Alan Hoerth')
        """
        self['yes_votes'].append(legislator)

    def no(self, legislator):
        """
        Indicate that a legislator (given as a string of their name) voted
        'no'.
        """
        self['no_votes'].append(legislator)

    def other(self, legislator):
        """
        Indicate that a legislator (given as a string of their name) abstained,
        voted 'present', or made any other vote not covered by 'yes' or 'no'.
        """
        self['other_votes'].append(legislator)

    def validate(self, standalone=True):
        super(Vote, self).validate()

        if standalone:
            self.validator.validate(self, self.standalone_schema)

            if self['session'] not in get_sessions(self['state']):
                raise ValueError("bad session: %s" % self['session'])

        if self['yes_votes'] or self['no_votes'] or self['other_votes']:
            # If we have *any* specific votes, then validate the counts
            # for all types.
            if len(self['yes_votes']) != self['yes_count']:
                raise ValueError("bad yes_vote count")
            if len(self['no_votes']) != self['no_count']:
                raise ValueError("bad no_vote count")
            if len(self['other_votes']) != self['other_count']:
                raise ValueError("bad other_vote count")
