import json

from django.db import models

from .model_factory import RegisterJSONEncoder


class ListField(models.CharField):
    # TODO: require register field parameter to enable type coercion; Field needs to be deconstructable
    # TODO: base code on django.contrib.postgres.fields.array.ArrayField
    # TODO: add form field

    def __init__(self, **kwargs):
        kwargs['max_length'] = kwargs.get('max_length', 255)
        kwargs['blank'] = True
        super().__init__(**kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if 'blank' in kwargs:
            del kwargs['blank']
        if kwargs.get('max_length') == 255:
            del kwargs['max_length']
        return name, path, args, kwargs

    def from_db_value(self, value, expression, connection, context):
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return json.loads(value)

    def to_python(self, value):
        if value is None or isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return json.loads(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if isinstance(value, (tuple, list)):
            return json.dumps(value, cls=RegisterJSONEncoder)
        return value
