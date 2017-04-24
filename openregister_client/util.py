import datetime
import logging
import re
from urllib.parse import urlparse, urlunparse

try:
    import markdown
except ImportError:
    markdown = None

try:
    from pytz import utc
except ImportError:
    class UTC(datetime.tzinfo):
        def __repr__(self):
            return '<UTC>'

        def utcoffset(self, dt):
            return datetime.timedelta(0)

        def tzname(self, dt):
            return 'UTC'

        def dst(self, dt):
            return datetime.timedelta(0)

    utc = UTC()

logger = logging.getLogger('.'.join(__name__.split('.')[:-1]))

re_datetime = re.compile(r'^(?P<year>\d\d\d\d)(?:-(?P<month>\d\d)(?:-(?P<day>\d\d)'
                         r'(?:T(?P<hour>\d\d)(?::(?P<minute>\d\d)(?::(?P<second>\d\d)Z?)?)?)?)?)?Z?$')
re_timestamp = re.compile(r'^(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)T'
                          r'(?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d)Z$')


# utility functions


def camel_case(name):
    """
    Turns a hyphenated word into camel-case
    :param name: string to convert
    """
    name = re.sub(r'-(\w)', lambda match: match.group(1).upper(), name.lower())
    return name[0].upper() + name[1:]


def now():
    """
    Aware 'now' in UTC
    """
    return datetime.datetime.utcnow().replace(tzinfo=utc)


# parsing functions


def parse_datetime(value):
    """
    Parses the datetime datatype, e.g. "2001-01-31" or "2001-01-31T23:20:55"
    TODO: work out contradiction between http://openregister.github.io/specification/#datetime-datatype
    and https://datatype.register.gov.uk/record/datetime regarding trailing Z
    :param value: a string to parse
    :return: datetime.datetime, datetime.date, YearMonth or Year
    """
    if isinstance(value, (datetime.date, YearMonth, Year)):
        return value
    if not isinstance(value, str):
        raise ValueError('value must be a str')
    matches = re_datetime.match(value)
    if not matches:
        raise ValueError('%s is not a valid datetime' % value)
    matches = {
        key: int(value)
        for key, value in matches.groupdict().items()
        if value is not None
    }
    if 'month' not in matches:
        return Year(**matches)
    if 'day' not in matches:
        return YearMonth(**matches)
    try:
        if 'hour' in matches:
            matches['tzinfo'] = utc
            return datetime.datetime(**matches)
        return datetime.date(**matches)
    except ValueError:
        raise ValueError('%s is not a valid datetime' % value)


def parse_text(value):
    """
    Converts a string to Markdown text which can be output as HTML
    :param value: a string to convert
    :return: parsed value
    """
    return Text('' if value is None else value)


def parse_timestamp(value):
    """
    Parses the timestamp datatype, e.g. "2001-01-31T23:20:55Z"
    :param value: a string to parse
    :return: parsed value
    """
    if isinstance(value, datetime.datetime):
        return value
    if not isinstance(value, str):
        raise ValueError('value must be a str')
    matches = re_timestamp.match(value)
    try:
        return datetime.datetime(*map(int, matches.groups()), tzinfo=utc)
    except (AttributeError, TypeError, ValueError):
        raise ValueError('%s is not a valid timestamp' % value)


def parse_item_hash(value):
    """
    Parses the item-hash datatype, e.g. sha-256:5b8e5ee02caedd0a6f3539b19d6b462dd2d08918764e7f476506996024f7b84a
    :param value: a string to parse
    :return: parsed value
    """
    if isinstance(value, ItemHash):
        return value
    if not isinstance(value, str):
        raise ValueError('value must be a str')
    return ItemHash(value)


def parse_url(value):
    """
    Parses the url datatype
    :param value: a string to parse
    :return: a normalised URL as a str
    """
    try:
        # TODO: add stricter checking? return a structured object?
        return urlunparse(urlparse(value))
    except ValueError:
        raise ValueError('%s is not a valid URL' % value)


def parse_curie(value):
    """
    Parses the curie datatype
    :param value: a string to parse
    :return: a normalised CURIE URL
    """
    if isinstance(value, Curie):
        return value
    if not isinstance(value, str):
        raise ValueError('value must be a str')
    return Curie(value)


# classes to represent register field data


class Year:
    """
    Represents a truncated datetime with just the year specified
    """
    __slots__ = ('year',)

    def __init__(self, year):
        self.year = year

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.year == self.year

    def __str__(self):
        return str(self.year)


class YearMonth:
    """
    Represents a truncated datetime with just the year and month specified
    """
    __slots__ = ('year', 'month')

    def __init__(self, year, month):
        self.year = year
        self.month = month

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.year == self.year and other.month == self.month

    def __str__(self):
        return '%d-%02d' % (self.year, self.month)


class Text(str):
    """
    Simple str subclass that can render Markdown as used in OpenRegister fields of text datatype
    NB: no guarantees are made about the safety of the HTML output
    """

    if markdown:
        @property
        def html(self):
            return markdown.markdown(self, output_format='html5')
    else:
        @property
        def html(self):
            logger.warning('Markdown support is not installed')
            return self


class ItemHash(str):
    """
    Structured string specifying a hash
    """

    def __init__(self, value):
        super().__init__()
        values = value.split(':')
        if len(values) != 2 or values[0] != 'sha-256' or len(values[1]) != 64:
            raise ValueError('%s is not a valid hash' % value)
        self.algorithm = values[0]
        self.value = values[1]


class Curie(str):
    """
    CURIE compact URL
    TODO: should more checking be done of prefix and reference against specification?
    """

    def __init__(self, value):
        super().__init__()
        if value.startswith('[') and value.endswith(']'):
            value = value[1:-1]
        values = value.split(':')
        if len(values) != 2:
            raise ValueError('%s is not a valid CURIE' % value)
        self.prefix = values[0]
        self.reference = values[1]

    def __str__(self):
        return '%s:%s' % (self.prefix, self.reference)

    @property
    def safe_format(self):
        return '[%s]' % self


class Descriptor:
    """
    A class attribute that performs an operation when retrieved and optionally caches the result
    """

    def __init__(self, cached=True):
        self.cached = cached

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        value = self.get_value(instance)
        if self.cached:
            instance.__dict__[self.name] = value
        return value

    def get_value(self, instance):
        raise NotImplementedError


class ClassDescriptor(Descriptor):
    """
    A class attribute for creating customised subclasses
    """

    def __init__(self, *base_classes, **kwargs):
        super().__init__(**kwargs)
        self.base_classes = base_classes

    def get_value(self, instance):
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        # typing hint
        pass
