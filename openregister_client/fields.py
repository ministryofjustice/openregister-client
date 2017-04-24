from .util import Descriptor, parse_curie, parse_datetime, parse_item_hash, parse_text, parse_timestamp,  parse_url


class Field(Descriptor):
    registry = dict()
    description = None

    # TODO: add desconstruct method for serialisation in migrations
    # TODO: add deserialisation method; reverse of coerce if possible

    @classmethod
    def __init_subclass__(cls, **kwargs):
        datatype = kwargs.get('datatype')
        if datatype:
            cls.registry[datatype] = cls

    @classmethod
    def get_field_for_datatype(cls, datatype):
        return cls.registry.get(datatype, cls)

    def __init__(self, data_path, nullable=False, required=True, cardinality='1', **kwargs):
        """
        Looks up values from the parent object's `data` attribute by following a key path
        :param data_path: .-separated key path through mapping-type objects
        :param nullable: whether the value can be None
        :param required: whether to raise an AttributeError if path is missing
        :param cardinality: 1 if a single value, n if multiple
        :param cached: replaces this attribute with the returned value
        """
        assert cardinality in ('1', 'n'), 'Invalid cardinality'
        super().__init__(**kwargs)
        self.data_path = data_path
        self.nullable = nullable
        self.required = required
        self.cardinality = cardinality

    def get_value(self, instance):
        value = instance
        try:
            for path_component in self.data_path.split('.'):
                value = value[path_component]
        except (KeyError, IndexError):
            if not self.required:
                return None
            raise AttributeError('Path %s does not exist' % self.data_path)
        if value is None:
            if self.nullable:
                return None
            raise AttributeError('Value cannot be None')
        if self.cardinality == 'n':
            return list(map(self.coerce, value))
        return self.coerce(value)

    def coerce(self, value):
        return value


class StringField(Field, datatype='string'):
    def coerce(self, value):
        return str(value)


class TextField(StringField, datatype='text'):
    def coerce(self, value):
        return parse_text(value)


class URLField(StringField, datatype='url'):
    def coerce(self, value):
        return parse_url(value)


class CurieField(StringField, datatype='curie'):
    def coerce(self, value):
        return parse_curie(value)


class HashField(StringField):
    def coerce(self, value):
        return parse_item_hash(value)


class IntegerField(Field, datatype='integer'):
    def coerce(self, value):
        return int(value)


class DateTimeField(Field, datatype='datetime'):
    def coerce(self, value):
        return parse_datetime(value)


class TimestampField(Field):
    def coerce(self, value):
        return parse_timestamp(value)
