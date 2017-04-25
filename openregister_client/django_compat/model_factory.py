import datetime
import json
import textwrap

try:
    from django.core.serializers.json import DjangoJSONEncoder as JSONEncoder
except ImportError:
    JSONEncoder = json.JSONEncoder

from ..fields import Field, StringField, TextField, URLField, IntegerField, DateTimeField, TimestampField
from ..registers import OpenRegister
from ..util import Year, YearMonth, camel_case, logger, utc

__all__ = ('ModelFactory',)


class RegisterJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, (Year, YearMonth)):
            return str(o)
        if isinstance(o, datetime.datetime):
            offset = o.utcoffset()
            if offset is None:
                raise ValueError('Cannot serialise naive datetime')
            elif offset:
                o = o.astimezone(utc)
            r = o.isoformat()
            if o.microsecond:
                r = r[:23] + r[26:]
            if r.endswith('+00:00'):
                r = r[:-6] + 'Z'
            return r
        if isinstance(o, datetime.date):
            return o.isoformat()
        return super().default(o)


class ModelFactory:
    field_mapping = {
        Field: {'class': 'models.CharField', 'kwargs': {'max_length': 255, 'blank': True}},
        StringField: {'class': 'models.CharField', 'kwargs': {'max_length': 255, 'blank': True}},
        TextField: {'class': 'models.TextField', 'kwargs': {'blank': True}},
        IntegerField: {'class': 'models.IntegerField', 'kwargs': {}},
        URLField: {'class': 'models.URLField', 'kwargs': {'max_length': 255}},
        DateTimeField: {'class': 'models.CharField', 'kwargs': {'max_length': 20}},  # TODO: make a better model field
        TimestampField: {'class': 'models.DateTimeField', 'kwargs': {}},
    }
    model_template = '''
{factory.import_statements}


class {factory.model_name}Manager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)

    def load_data_from_register(self, clear=False):
        if clear:
            self.all().delete()
        register = self.model.get_register_client()
        for record in register.get_records():
            item = record.item
            self.create(
                key=record.key,
                {factory.copy_record_item}
            )


class {factory.model_name}(models.Model):
    """
    Represents items stored in the "{factory.register.name}" register
    """
    key = models.CharField(primary_key=True, max_length=255)

    {factory.fields}

    objects = {factory.model_name}Manager()

    @classmethod
    def get_register_url(cls):
        return {factory.register.base_url!r}

    {factory.register_methods}

    def __repr__(self):
        return '<{factory.model_name} %s>' % self.key

    def natural_key(self):
        return self.key,
    '''

    def __init__(self, register):
        if not isinstance(register, OpenRegister):
            raise ValueError('Cannot create a model from this type')
        if register.__class__ == OpenRegister:
            logger.warning('Using OpenRegister instances directly does not use field/datatype discovery '
                           'so may create incorrect model fields')
        if register.name == 'register':
            logger.warning('Register model name may conflict with OpenRegister client')
        self.register = register
        self.can_make_root_register = (hasattr(register, 'get_root_register') and
                                       isinstance(self.register.get_root_register().url_template, str))

    @property
    def import_statements(self):
        statements = [
            'from django.db import models',
            '',
        ]
        if any(register_field.cardinality != '1' for register_field in self.get_item_fields()):
            statements.append('from openregister_client.django_compat.fields import ListField')
        if self.can_make_root_register:
            statements.append('from openregister_client.registers import Register')
        else:
            statements.append('from openregister_client.registers import OpenRegister')
        return '\n'.join(statements)

    @property
    def model_name(self):
        return camel_case(self.register.name)

    def get_item_fields(self):
        item_class = self.register.item_class
        for item_field in item_class.__dict__.keys():  # NB: dir does not preserve field order
            item_field = getattr(item_class, item_field, None)
            if isinstance(item_field, Field):
                yield item_field

    def get_model_field(self, register_field):
        model_field = None
        register_field_cls = register_field.__class__

        if register_field.cardinality != '1':
            model_field_kwargs = {}
            if register_field.nullable or not register_field.required:
                model_field_kwargs['null'] = True
            return 'ListField', model_field_kwargs

        for register_field_cls in [register_field_cls] + register_field_cls.mro():
            if register_field_cls in self.field_mapping:
                model_field = self.field_mapping[register_field_cls]
                break
        if not model_field:
            logger.warning('Register field %s does not have a known model field type' % register_field.name)
            model_field = self.field_mapping[Field]
        elif register_field_cls == Field:
            logger.warning('Register field %s uses generic model field type' % register_field.name)
        model_field_kwargs = model_field['kwargs'].copy()
        if register_field.nullable or not register_field.required:
            model_field_kwargs['null'] = True
        return model_field['class'], model_field_kwargs

    @property
    def fields(self):
        fields = []
        for register_field in self.get_item_fields():
            model_field_class, model_field_kwargs = self.get_model_field(register_field)
            model_field_kwargs = ', '.join(
                '%s=%r' % (key, value)
                for key, value in model_field_kwargs.items()
            )
            fields.append('%s = %s(%s)' % (register_field.name, model_field_class, model_field_kwargs))
        return '\n    '.join(fields).strip()

    @property
    def register_methods(self):
        if not self.can_make_root_register:
            return '''
    @classmethod
    def get_register_client(cls):
        return OpenRegister(name={register.name!r}, base_url={register.base_url!r})
        '''.format(register=self.register).strip()

        return '''
    @classmethod
    def get_register_client(cls):
        return cls.get_root_register_client().get_register({register.name!r})

    @classmethod
    def get_root_register_url(cls):
        return {root_register.base_url!r}

    @classmethod
    def get_root_register_client(cls):
        return Register(name={root_register.name!r}, url_template={root_register.url_template!r})
        '''.format(register=self.register, root_register=self.register.get_root_register()).strip()

    @property
    def copy_record_item(self):
        return ',\n                '.join(
            '%s=item.%s' % (field.name, field.name)
            for field in self.get_item_fields()
        )

    def get_model_code(self):
        return textwrap.dedent(self.model_template.format(factory=self)).strip() + '\n'

    def write_fixtures_from_register(self, model_name, file_or_stream, close_on_exit=False):
        field_names = [field.name for field in self.get_item_fields()]
        records = [
            {
                'model': model_name,
                'pk': record.key,
                'fields': {
                    field: getattr(record.item, field)
                    for field in field_names
                }
            }
            for record in self.register.get_records()
        ]
        try:
            if isinstance(file_or_stream, str):
                close_on_exit = True
                file_or_stream = open(file_or_stream, mode='wt', encoding='utf-8')
            json.dump(records, file_or_stream, cls=RegisterJSONEncoder, indent=4)
        finally:
            if close_on_exit:
                file_or_stream.close()
