import datetime
try:
    from collections.abc import Mapping
except ImportError:
    from collections import Mapping
from urllib.parse import urljoin, quote as urlquote

import requests

from . import __version__
from .fields import Field, HashField, IntegerField, StringField, TextField, TimestampField
from .util import ClassDescriptor, Descriptor, camel_case, logger, parse_curie, now

__all__ = ('OpenRegister', 'Register', 'AlphaRegister')

user_agent = 'openregister-client/%s' % __version__
not_found = object()


class Resource(dict):
    pass


class BaseItem(Resource):
    pass


class TimedItemMixin:
    @property
    def is_current(self):
        start_date = getattr(self, 'start_date')
        end_date = getattr(self, 'end_date')
        this_moment = now()
        this_moment_str = '%sZ' % this_moment.isoformat(timespec='seconds')
        if start_date and type(start_date) == type(end_date):
            if isinstance(start_date, str):
                this_moment = this_moment_str
            elif not isinstance(start_date, datetime.datetime):
                this_moment = this_moment.today()
            return start_date <= this_moment <= end_date
        if start_date:
            if isinstance(start_date, str):
                this_moment = this_moment_str
            elif not isinstance(start_date, datetime.datetime):
                this_moment = this_moment.today()
            return start_date <= this_moment
        if end_date:
            if isinstance(end_date, str):
                this_moment = this_moment_str
            elif not isinstance(end_date, datetime.datetime):
                this_moment = this_moment.today()
            return this_moment <= end_date
        return True


class ItemClassDescriptor(ClassDescriptor):
    def get_value(self, instance):
        base_classes = self.base_classes
        field_names = instance.register_info.fields
        if 'start-date' in field_names or 'end-date' in field_names:
            base_classes += (TimedItemMixin,)

        class RegisterItem(*base_classes):
            pass

        for field_name in field_names:
            attr_name = field_name.replace('-', '_')
            attr = instance.make_field(field_name)
            attr.__set_name__(RegisterItem, attr_name)  # presumably only called automatically at class creation
            if hasattr(RegisterItem, attr_name):
                if isinstance(getattr(RegisterItem, attr_name), Field):
                    # assume item subclass already does the right thing
                    continue
                logger.warning('overriding existing record attribute "%s" '
                               'with a value field for "%s" register' % (attr_name, instance.name))
            setattr(RegisterItem, attr_name, attr)

        RegisterItem.__name__ = '%sItem' % camel_case(instance.name)
        return RegisterItem


class BaseEntry(Resource):
    key = StringField('key')  # type: str
    index_entry_number = IntegerField('index-entry-number')  # type: int
    entry_number = IntegerField('entry-number')  # type: int
    entry_timestamp = TimestampField('entry-timestamp')  # type: datetime.datetime
    item_hashes = HashField('item-hash', cardinality='n')  # type: list

    # TODO: how does index-entry-number differ from entry-number?

    def get_items(self):
        # use parent register to look up item hashes
        raise NotImplementedError


class EntryClassDescriptor(ClassDescriptor):
    def get_value(self, instance):
        class Entry(*self.base_classes):
            def get_items(self):
                yield from map(instance.get_item, self.item_hashes)

        Entry.__name__ = '%sEntry' % camel_case(instance.name)
        return Entry


class BaseRecord(Resource):
    key = StringField('key')  # type: str
    index_entry_number = IntegerField('index-entry-number')  # type: int
    entry_number = IntegerField('entry-number')  # type: int
    entry_timestamp = TimestampField('entry-timestamp')  # type: datetime.datetime
    items = NotImplemented  # type: list

    # TODO: how does index-entry-number differ from entry-number?

    @property
    def item(self):
        items = self.items
        if len(items) == 1:
            return items[0]
        raise ValueError('There is not exactly one item in this record')

    def get_entries(self):
        # use parent register to look up entries
        raise NotImplementedError


class RecordClassDescriptor(ClassDescriptor):
    def get_value(self, instance):
        class ItemField(Field):
            def coerce(self, value):
                return instance.item_class(value)

        class Record(*self.base_classes):
            items = ItemField('item', cardinality='n')  # type: list

            def get_entries(self):
                # NB: no pagination
                url = instance.expand_url_path('record/%s/entries' % self.key)
                data_list = instance.request(url)
                if data_list is not_found:
                    raise ValueError('Record entries response has no data')
                yield from map(instance.entry_class, data_list)

        Record.__name__ = '%sRecord' % camel_case(instance.name)
        return Record


class RegisterInfo(Resource):
    total_records = IntegerField('total-records')  # type: int
    total_entries = IntegerField('total-entries')  # type: int
    last_updated = TimestampField('last-updated')  # type: datetime.datetime
    domain = StringField('domain')  # type: str

    # NB: some fields are renamed for clarity, entry-specific fields not included
    fields = StringField('register-record.fields', cardinality='n')  # type: list
    register = StringField('register-record.register')  # type: str
    description = StringField('register-record.text')  # type: str
    phase = StringField('register-record.phase')  # type: str
    registry = StringField('register-record.registry')  # type: str
    copyright = TextField('register-record.copyright', required=False)  # type: str

    # TODO: register.register_info.register should equal register.name so one could be dropped


class RequestDescriptor(Descriptor):
    def __init__(self, url_path, register_object_class, **kwargs):
        super().__init__(**kwargs)
        self.url_path = url_path
        self.register_object_class = register_object_class

    def get_value(self, instance):
        url = instance.expand_url_path(self.url_path)
        data = instance.request(url)
        if data is not_found:
            raise ValueError('Cannot load data at %s' % self.url_path)
        return self.register_object_class(data)


class OpenRegister:
    """
    OpenRegister client that loads data directly from a register without datatype discovery
    """
    register_info = RequestDescriptor('register', RegisterInfo)  # type: RegisterInfo
    item_class = ItemClassDescriptor(BaseItem)  # type: type
    entry_class = EntryClassDescriptor(BaseEntry)  # type: type
    record_class = RecordClassDescriptor(BaseRecord)  # type: type

    def __init__(self, name, base_url=None, api_key=None):
        if not base_url:
            base_url = 'https://%s.register.gov.uk/' % name
        self.name = name
        self.base_url = base_url
        self.api_key = api_key

    def __repr__(self):
        return '<Register %s>' % self.name

    def __len__(self):
        return self.register_info.total_records

    def __iter__(self):
        yield from self.get_records()

    def __contains__(self, key):
        return self.get_record(key) is not None

    def make_field(self, field_name):
        return Field(field_name, nullable=True, required=False)

    def expand_url_path(self, path):
        return urljoin(self.base_url, path)

    @property
    def request_headers(self):
        headers = {
            'user-agent': user_agent,
            'accept': 'application/json',
        }
        if self.api_key:
            headers['authorization'] = self.api_key
        return headers

    def request(self, url, params=None):
        logger.debug('Requesting %s with params: %s' % (url, params))
        response = requests.get(url=url, params=params, headers=self.request_headers)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return not_found
        raise ValueError('request %s returned status %s' % (url, response.status_code))

    def get_records(self, filters=None, page_size=None):
        # NB: uses page-based pagination (increments by 1)
        if filters:
            assert isinstance(filters, Mapping) and len(filters) == 1, 'filters must be a mapping with 1 item'
            url = map(urlquote, next(iter(filters.items())))
            url = 'records/%s/%s' % tuple(url)
        else:
            url = 'records'
        params = {'page-index': 1}
        if page_size:
            params['page-size'] = page_size
        while True:
            data_list = self.request(self.expand_url_path(url), params=params)
            if data_list is not_found:
                # TODO: do not paginate beyond expected end, but raise ValueError for not_found otherwise
                return
            yield from map(self.record_class, data_list.values())
            params['page-index'] += 1

    def get_record(self, key):
        url = self.expand_url_path('record/%s' % key)
        data = self.request(url)
        if data is not_found:
            return None
        try:
            return self.record_class(data[key])
        except (KeyError, TypeError):
            raise ValueError('Record response does not contain key')

    def get_entries(self, page_size=100):
        # NB: uses limit-based pagination (increments by page size)
        params = {
            'start': 1,
            'limit': page_size,
        }
        while True:
            url = self.expand_url_path('entries')
            data_list = self.request(url, params=params)
            if data_list is not_found:
                # TODO: do not paginate beyond expected end, but raise ValueError for not_found otherwise
                return
            yield from map(self.entry_class, data_list)
            params['start'] += page_size

    def get_entry(self, entry_number):
        url = self.expand_url_path('entry/%s' % entry_number)
        data = self.request(url)
        if data is not_found:
            return None
        assert isinstance(data, list) and len(data) == 1, 'Entry response should be a list of 1 entry'
        return self.entry_class(data[0])

    # def get_items(self):
    #     raise NotImplementedError('open registers’ items cannot be enumerated')

    def get_item(self, item_hash):
        url = self.expand_url_path('item/%s' % item_hash)
        data = self.request(url)
        if data is not_found:
            return None
        return self.item_class(data)


class Register(OpenRegister):
    """
    OpenRegister client that uses the root "register" register to discover fields and their datatypes;
    listing registers that are at least in beta
    """
    url_template = 'https://%(name)s.register.gov.uk/'

    def __init__(self, name='register', url_template=None, api_key=None):
        self.url_template = url_template or self.url_template
        super().__init__(name=name, base_url=self.make_register_url(name), api_key=api_key)
        self.discover_complete = False
        self.field_registry = {}
        datatype_register = self.get_register('datatype')
        field_register = self.get_register('field')
        if datatype_register and field_register:
            self.discover_fields(datatype_register, field_register)
            self.discover_complete = True
        else:
            logger.warning('Register is missing datatype or field registers')

    def get_root_register(self):
        return self

    def make_register_url(self, name):
        if isinstance(self.url_template, str):
            return self.url_template % {'name': name}
        return self.url_template(name)

    def discover_fields(self, datatype_register, field_register):
        for record in datatype_register:
            datatype = record.item.datatype
            field_cls = Field.registry.get(datatype)
            if field_cls:
                field_cls.description = record.item.text
            else:
                logger.warning('Missing datatype to field mapping for `%s`' % datatype)
        for record in field_register:
            field_name = record.item.field
            datatype = record.item.datatype
            field_cls = Field.registry.get(datatype, Field)
            if field_cls is Field:
                logger.warning('Missing `%s` field datatype to field mapping' % field_name)
            self.field_registry[field_name] = dict(
                field_cls=field_cls,
                cardinality=record.item.cardinality,
                description=record.item.text,
            )

    def make_field(self, field_name):
        if field_name in self.field_registry:
            registered_field = self.field_registry[field_name]
            field_cls = registered_field['field_cls']
            return field_cls(field_name, nullable=True, required=False, cardinality=registered_field['cardinality'])
        logger.warning('Register includes field %s not listed in field mapping' % field_name)
        return super().make_field(field_name)

    def make_register(self, name):
        if self.discover_complete:
            root_register = self

            class NewRegister(OpenRegister):
                field_registry = self.field_registry
                make_field = self.make_field

                def get_root_register(self):
                    return root_register

            NewRegister.__name__ = '%sRegister' % camel_case(name)
            NewRegister.__module__ = self.__module__
            register_cls = NewRegister
        else:
            register_cls = OpenRegister
        return register_cls(name, base_url=self.make_register_url(name), api_key=self.api_key)

    def get_registers(self, filters=None, page_size=None):
        yield from map(self.make_register, (
            record.item.register
            for record in self.get_records(filters=filters, page_size=page_size)
        ))

    def get_register(self, name):
        if name in self:
            return self.make_register(name)

    def get_record_using_curie(self, curie_url):
        curie_url = parse_curie(curie_url)
        register = self.get_register(curie_url.prefix)
        return register.get_record(curie_url.reference)

    def expand_curie(self, curie_url):
        curie_url = parse_curie(curie_url)
        return urljoin(self.make_register_url(curie_url.prefix), 'records/%s' % curie_url.reference)


class AlphaRegister(Register):
    """
    OpenRegister client that uses the root "register" register to discover fields and their datatypes;
    listing alpha-phase registers
    """
    url_template = 'https://%(name)s.alpha.openregister.org/'
