import datetime
import os
import unittest

import responses

from openregister_client.registers import BaseEntry, BaseItem, BaseRecord, ItemClassDescriptor, OpenRegister, Register
from openregister_client.util import utc


class CountryItem(BaseItem):
    @property
    def citizen_names_list(self):
        citizen_names = getattr(self, 'citizen_names', '')
        return citizen_names.split(';')


class Country(OpenRegister):
    item_class = ItemClassDescriptor(CountryItem)

    def __init__(self):
        super().__init__(name='country')


class ClientTestCase(unittest.TestCase):
    required_entry_keys = {'index-entry-number', 'entry-number', 'entry-timestamp', 'key', 'item-hash'}
    country_register_response = {
        'domain': 'register.gov.uk',
        'total-records': 199,
        'total-entries': 206,
        'register-record': {
            'fields': ['country', 'name', 'official-name', 'citizen-names', 'start-date', 'end-date'],
            'registry': 'foreign-commonwealth-office',
            'text': 'British English-language names and descriptive terms for countries',
            'phase': 'beta',
            'register': 'country',
            'entry-timestamp': '2016-08-04T14:45:41Z',
            'key': 'country',
            'index-entry-number': '2',
            'entry-number': '2',
        },
        'last-updated': '2017-03-29T14:22:30Z',
    }
    country_record_response = {
        'GB': {
            'index-entry-number': '6',
            'entry-number': '6',
            'entry-timestamp': '2016-04-05T13:23:05Z',
            'key': 'GB',
            'item': [
                {
                    'country': 'GB',
                    'official-name': 'The United Kingdom of Great Britain and Northern Ireland',
                    'name': 'United Kingdom',
                    'citizen-names': 'Briton;British citizen',
                }
            ]
        }
    }
    country_entry_response = [
        {
            'index-entry-number': '6',
            'entry-number': '6',
            'entry-timestamp': '2016-04-05T13:23:05Z',
            'key': 'GB',
            'item-hash': ['sha-256:6b18693874513ba13da54d61aafa7cad0c8f5573f3431d6f1c04b07ddb27d6bb'],
        }
    ]
    country_item_response = {
        'country': 'GB',
        'official-name': 'The United Kingdom of Great Britain and Northern Ireland',
        'name': 'United Kingdom',
        'citizen-names': 'Briton;British citizen',
    }

    def test_creating_register_does_not_load_data(self):
        with self.assertRaises(AssertionError) as manager:
            with responses.RequestsMock() as rsps:
                rsps.add(rsps.GET, 'https://country.register.gov.uk/register', json=self.country_register_response)
                register = Country()
            self.assertIn('domain', dir(register))
        self.assertIn('Not all requests have been executed', str(manager.exception),
                      'Register info should be lazily loaded')

    def test_register_info_data_loading(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/register', json=self.country_register_response)
            register = Country()
            register_info = register.register_info
            # basic info
            self.assertEqual(len(register), 199)
            self.assertEqual(register_info.domain, 'register.gov.uk')
            self.assertEqual(register_info.total_records, 199)
            self.assertEqual(register_info.total_entries, 206)
            self.assertEqual(register_info.last_updated,
                             datetime.datetime(2017, 3, 29, 14, 22, 30, tzinfo=utc))
            # register record (as would be received from "register" register)
            self.assertEqual(register_info.register, 'country')
            self.assertEqual(register_info.register, register.name)
            self.assertEqual(register_info.phase, 'beta')
            self.assertEqual(register_info.registry, 'foreign-commonwealth-office')
            self.assertEqual(register_info.description,
                             'British English-language names and descriptive terms for countries')
            self.assertSequenceEqual(register_info.fields,
                                     ['country', 'name', 'official-name', 'citizen-names', 'start-date', 'end-date'])

    def test_record_loading(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/record/GB', json=self.country_record_response)
            register = Country()
            record = register.get_record('GB')
        # type check
        self.assertIsInstance(record, BaseRecord)
        self.assertIsInstance(record.item, BaseItem)
        # generic Record attributes
        self.assertEqual(record.key, 'GB')
        self.assertEqual(record.entry_number, 6)  # entry numbers are coerced into int
        self.assertEqual(record.entry_timestamp.date(), datetime.date(2016, 4, 5))
        self.assertEqual(record.item.country, 'GB')
        # special CountryRecord attributes
        self.assertTrue(record.item.is_current)
        self.assertSequenceEqual(record.item.citizen_names_list, ['Briton', 'British citizen'])

    def test_entry_loading(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/entry/6', json=self.country_entry_response)
            country_register = Country()
            entry = country_register.get_entry(6)
        # type check
        self.assertIsInstance(entry, BaseEntry)
        # Entry attributes
        self.assertTrue(all(key in entry for key in self.required_entry_keys))
        self.assertEqual(entry.entry_number, 6)
        self.assertEqual(entry.entry_timestamp.date(), datetime.date(2016, 4, 5))
        self.assertSequenceEqual(entry.item_hashes,
                                 ['sha-256:6b18693874513ba13da54d61aafa7cad0c8f5573f3431d6f1c04b07ddb27d6bb'])

    def test_item_loading(self):
        item_hash = 'sha-256:6b18693874513ba13da54d61aafa7cad0c8f5573f3431d6f1c04b07ddb27d6bb'
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/item/%s' % item_hash,
                     json=self.country_item_response)
            rsps.add(rsps.GET, 'https://country.register.gov.uk/register', json=self.country_register_response)
            register = Country()
            item = register.get_item(item_hash)
        # type check
        self.assertIsInstance(item, BaseItem)
        # Item attributes
        self.assertFalse(any(key in item for key in self.required_entry_keys))
        self.assertDictEqual(item, self.country_item_response)

    def test_record_iteration(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/records', json=self.country_record_response)
            rsps.add(rsps.GET, 'https://country.register.gov.uk/records', status=404)
            register = Country()
            record_list = list(register.get_records())
        self.assertSequenceEqual([dict(record) for record in record_list],
                                 [self.country_record_response['GB']])

    def test_record_item_loading(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/records', json=self.country_record_response)
            rsps.add(rsps.GET, 'https://country.register.gov.uk/register', json=self.country_register_response)
            register = Country()
            record = next(register.get_records())
            record_item = record.item
        self.assertDictEqual(dict(record_item), self.country_item_response)

    def test_filtered_record_iteration(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/records/name/United%20Kingdom',
                     json=self.country_record_response)
            rsps.add(rsps.GET, 'https://country.register.gov.uk/records/name/United%20Kingdom', status=404)
            register = Country()
            record_list = list(register.get_records(filters={'name': 'United Kingdom'}))
        self.assertSequenceEqual([dict(record) for record in record_list],
                                 [self.country_record_response['GB']])

        # invalid filtering
        with responses.RequestsMock(), self.assertRaises(AssertionError) as manager:
            list(register.get_records(filters={'name': 'United Kingdom', 'official-name': 'United Kingdom'}))
        self.assertIn('filters must be a mapping with 1 item', str(manager.exception))
        with responses.RequestsMock(), self.assertRaises(AssertionError) as manager:
            list(register.get_records(filters=('name', 'United Kingdom')))
        self.assertIn('filters must be a mapping with 1 item', str(manager.exception))
        with responses.RequestsMock(), self.assertRaises(AssertionError) as manager:
            list(register.get_records(filters='name=United Kingdom'))
        self.assertIn('filters must be a mapping with 1 item', str(manager.exception))

    def test_entry_iteration(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://country.register.gov.uk/entries', json=self.country_entry_response)
            rsps.add(rsps.GET, 'https://country.register.gov.uk/entries', status=404)
            register = Country()
            entry_list = list(register.get_entries())
        self.assertSequenceEqual([dict(entry) for entry in entry_list], self.country_entry_response)

    def test_register_discovery(self):
        with responses.RequestsMock() as rsps:
            rsps.add(rsps.GET, 'https://register.register.gov.uk/record/datatype', json={
                'datatype': {
                    'index-entry-number': '3',
                    'entry-number': '3',
                    'entry-timestamp': '2016-08-04T14:45:41Z',
                    'key': 'datatype',
                    'item': [
                        {
                            'phase': 'beta',
                            'registry': 'cabinet-office',
                            'text': 'Datatypes constraining values used by register fields and idenitifying '
                                    'ways in which it may be encoded a representation',
                            'fields': ['datatype', 'phase', 'text'],
                            'register': 'datatype'
                        }
                    ]
                }
            })
            rsps.add(rsps.GET, 'https://register.register.gov.uk/record/field', json={
                'field': {
                    'index-entry-number': '4',
                    'entry-number': '4',
                    'entry-timestamp': '2016-08-04T14:45:41Z',
                    'key': 'field',
                    'item': [
                        {
                            'phase': 'beta',
                            'registry': 'cabinet-office',
                            'text': 'Field names which may appear in a register',
                            'fields': ['field', 'datatype', 'phase', 'register', 'cardinality', 'text'],
                            'register': 'field'
                        }
                    ]
                }
            })
            rsps.add(rsps.GET, 'https://datatype.register.gov.uk/register', json={
                'domain': 'register.gov.uk',
                'total-records': 3,
                'total-entries': 3,
                'register-record': {
                    'fields': ['datatype', 'phase', 'text'],
                    'registry': 'cabinet-office',
                    'text': 'Datatypes constraining values used by register fields and idenitifying '
                            'ways in which it may be encoded a representation',
                    'phase': 'beta',
                    'register': 'datatype',
                    'entry-timestamp': '2016-08-04T14:45:41Z',
                    'key': 'datatype',
                    'index-entry-number': '3',
                    'entry-number': '3'
                },
                'last-updated': '2016-08-04T14:09:48Z'
            })
            rsps.add(rsps.GET, 'https://datatype.register.gov.uk/records', json={
                'string': {
                    'index-entry-number': '2',
                    'entry-number': '2',
                    'entry-timestamp': '2016-08-04T14:09:48Z',
                    'key': 'string',
                    'item': [
                        {
                            'phase': 'beta',
                            'datatype': 'string',
                            'text': 'A string of [Unicode 6.2.x](http://www.unicode.org/versions/Unicode6.2.0/) '
                                    'characters encoded as [UTF-8](http://en.wikipedia.org/wiki/UTF-8).'
                        }
                    ]
                },
                'datetime': {
                    'index-entry-number': '3',
                    'entry-number': '3',
                    'entry-timestamp': '2016-08-04T14:09:48Z',
                    'key': 'datetime',
                    'item': [
                        {
                            'phase': 'beta',
                            'datatype': 'datetime',
                            'text': 'A combination of a date and a time in the format `CCYY-MM-DDThh:mm:ss[Z]` '
                                    'as described in chapter 5.4 of [ISO 8601]'
                                    '(http://en.wikipedia.org/wiki/ISO_8601). The value can be truncated to '
                                    'just the most significant digits, for example \'2014-05\'. '
                                    'Time values, where present, should be in UTC.'
                        }
                    ]
                },
                'text': {
                    'index-entry-number': '1',
                    'entry-number': '1',
                    'entry-timestamp': '2016-08-04T14:09:48Z',
                    'key': 'text',
                    'item': [
                        {
                            'phase': 'beta',
                            'datatype': 'text',
                            'text': 'A string of text which may contain [Markdown]'
                                    '(http://en.wikipedia.org/wiki/Markdown) formatting instructions.'
                        }
                    ]
                }
            })
            rsps.add(rsps.GET, 'https://datatype.register.gov.uk/records', status=404)
            rsps.add(rsps.GET, 'https://field.register.gov.uk/register', json={
                'domain': 'register.gov.uk',
                'total-records': 22,
                'total-entries': 42,
                'register-record': {
                    'fields': ['field', 'datatype', 'phase', 'register', 'cardinality', 'text'],
                    'registry': 'cabinet-office',
                    'text': 'Field names which may appear in a register',
                    'phase': 'beta',
                    'register': 'field',
                    'entry-timestamp': '2016-08-04T14:45:41Z',
                    'key': 'field',
                    'index-entry-number': '4',
                    'entry-number': '4'
                },
                'last-updated': '2017-04-06T06:54:10Z'
            })
            rsps.add(rsps.GET, 'https://field.register.gov.uk/records', json={
                'phase': {
                    'index-entry-number': '33',
                    'entry-number': '33',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'phase',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'phase',
                            'datatype': 'string',
                            'text': 'The stage of development a register is in. '
                                    'There are 4 phases - discovery, alpha, beta and live.',
                            'cardinality': '1'
                        }
                    ]
                },
                'registry': {
                    'index-entry-number': '35',
                    'entry-number': '35',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'registry',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'registry',
                            'datatype': 'string',
                            'text': 'The organisation responsible for the data in a register. '
                                    'The custodian is usually from the registry.',
                            'cardinality': '1'
                        }
                    ]
                },
                'local-authority-type': {
                    'index-entry-number': '30',
                    'entry-number': '30',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'local-authority-type',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'local-authority-type',
                            'datatype': 'string',
                            'text': 'The type of local government organisation.',
                            'cardinality': '1',
                            'register': 'local-authority-type'
                        }
                    ]
                },
                'country': {
                    'index-entry-number': '24',
                    'entry-number': '24',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'country',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'country',
                            'datatype': 'string',
                            'text': 'The country’s 2-letter ISO 3166-2 alpha2 code.',
                            'cardinality': '1',
                            'register': 'country'
                        }
                    ]
                },
                'copyright': {
                    'index-entry-number': '23',
                    'entry-number': '23',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'copyright',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'copyright',
                            'datatype': 'text',
                            'text': 'The copyright and licensing terms which may apply to the data held in a register.',
                            'cardinality': '1'
                        }
                    ]
                },
                'start-date': {
                    'index-entry-number': '36',
                    'entry-number': '36',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'start-date',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'start-date',
                            'datatype': 'datetime',
                            'text': 'The date a record first became relevant to a register. '
                                    'For example, the date a country was first recognised by the UK.',
                            'cardinality': '1'
                        }
                    ]
                },
                'citizen-names': {
                    'index-entry-number': '22',
                    'entry-number': '22',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'citizen-names',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'citizen-names',
                            'datatype': 'string',
                            'text': 'The name of a country’s citizens.',
                            'cardinality': '1'
                        }
                    ]
                },
                'cardinality': {
                    'index-entry-number': '21',
                    'entry-number': '21',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'cardinality',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'cardinality',
                            'datatype': 'string',
                            'text': 'A character (either "1" or "n") that explains if '
                                    'a field in a register can contain multiple values.',
                            'cardinality': '1'
                        }
                    ]
                },
                'end-date': {
                    'index-entry-number': '26',
                    'entry-number': '26',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'end-date',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'end-date',
                            'datatype': 'datetime',
                            'text': 'The date a record stopped being applicable. '
                                    'For example, the date a school closed down.',
                            'cardinality': '1'
                        }
                    ]
                },
                'official-name': {
                    'index-entry-number': '32',
                    'entry-number': '32',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'official-name',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'official-name',
                            'datatype': 'string',
                            'text': 'The official or technical name of a record.',
                            'cardinality': '1'
                        }
                    ]
                },
                'internal-drainage-board': {
                    'index-entry-number': '39',
                    'entry-number': '39',
                    'entry-timestamp': '2017-04-06T06:54:10Z',
                    'key': 'internal-drainage-board',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'internal-drainage-board',
                            'datatype': 'string',
                            'text': 'Internal drainage board code.',
                            'cardinality': '1',
                            'register': 'internal-drainage-board'
                        }
                    ]
                },
                'field': {
                    'index-entry-number': '27',
                    'entry-number': '27',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'field',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'field',
                            'datatype': 'string',
                            'text': 'The name of a field. A field can appear in more than one register.',
                            'cardinality': '1',
                            'register': 'field'
                        }
                    ]
                },
                'datatype': {
                    'index-entry-number': '25',
                    'entry-number': '25',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'datatype',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'datatype',
                            'datatype': 'string',
                            'text': 'The format of the data held in a field.',
                            'cardinality': '1',
                            'register': 'datatype'
                        }
                    ]
                },
                'registration-district': {
                    'index-entry-number': '42',
                    'entry-number': '42',
                    'entry-timestamp': '2017-04-06T06:54:10Z',
                    'key': 'registration-district',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'registration-district',
                            'datatype': 'string',
                            'text': 'The code for a registration district in England or Wales.',
                            'cardinality': '1',
                            'register': 'registration-district'
                        }
                    ]
                },
                'local-authority-eng': {
                    'index-entry-number': '29',
                    'entry-number': '29',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'local-authority-eng',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'local-authority-eng',
                            'datatype': 'string',
                            'text': 'The local authority’s ISO 3166-1 alpha3 code. '
                                    'Unique codes have been created for local authorities that '
                                    'don’t have an existing ISO code.',
                            'cardinality': '1',
                            'register': 'local-authority-eng'
                        }
                    ]
                },
                'name': {
                    'index-entry-number': '31',
                    'entry-number': '31',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'name',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'name',
                            'datatype': 'string',
                            'text': 'The commonly-used name of a record.',
                            'cardinality': '1'
                        }
                    ]
                },
                'name-cy': {
                    'index-entry-number': '41',
                    'entry-number': '41',
                    'entry-timestamp': '2017-04-06T06:54:10Z',
                    'key': 'name-cy',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'name-cy',
                            'datatype': 'string',
                            'text': 'Welsh name for an entry.',
                            'cardinality': '1'
                        }
                    ]
                },
                'text': {
                    'index-entry-number': '38',
                    'entry-number': '38',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'text',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'text',
                            'datatype': 'text',
                            'text': 'Notes and other additional information about a record in a register.',
                            'cardinality': '1'
                        }
                    ]
                },
                'fields': {
                    'index-entry-number': '28',
                    'entry-number': '28',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'fields',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'fields',
                            'datatype': 'string',
                            'text': 'The names of the fields in register.',
                            'cardinality': 'n',
                            'register': 'field'
                        }
                    ]
                },
                'legislation': {
                    'index-entry-number': '40',
                    'entry-number': '40',
                    'entry-timestamp': '2017-04-06T06:54:10Z',
                    'key': 'legislation',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'legislation',
                            'datatype': 'string',
                            'text': 'The identifier for the Statutory Instrument establishing '
                                    'the board’s powers and duties (where known).',
                            'cardinality': '1'
                        }
                    ]
                },
                'territory': {
                    'index-entry-number': '37',
                    'entry-number': '37',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'territory',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'territory',
                            'datatype': 'string',
                            'text': 'The territory’s ISO 3166-1 alpha3 code. Unique codes have been created '
                                    'for territories that don’t have an existing ISO code.',
                            'cardinality': '1',
                            'register': 'territory'
                        }
                    ]
                },
                'register': {
                    'index-entry-number': '34',
                    'entry-number': '34',
                    'entry-timestamp': '2017-01-10T17:16:07Z',
                    'key': 'register',
                    'item': [
                        {
                            'phase': 'beta',
                            'field': 'register',
                            'datatype': 'string',
                            'text': 'The name of a register.',
                            'cardinality': '1',
                            'register': 'register'
                        }
                    ]
                }
            })
            rsps.add(rsps.GET, 'https://field.register.gov.uk/records', status=404)
            rsps.add(rsps.GET, 'https://register.register.gov.uk/record/country', json={
                'country': {
                    'index-entry-number': '2',
                    'entry-number': '2',
                    'entry-timestamp': '2016-08-04T14:45:41Z',
                    'key': 'country',
                    'item': [
                        {
                            'phase': 'beta',
                            'registry': 'foreign-commonwealth-office',
                            'text': 'British English-language names and descriptive terms for countries',
                            'fields': ['country', 'name', 'official-name', 'citizen-names', 'start-date', 'end-date'],
                            'register': 'country'
                        }
                    ]
                }
            })
            rsps.add(rsps.GET, 'https://country.register.gov.uk/record/GB', json=self.country_record_response)
            rsps.add(rsps.GET, 'https://country.register.gov.uk/register', json=self.country_register_response)
            register = Register()
            country_register = register.get_register('country')
            record = country_register.get_record('GB')
            record_item = record.item
        self.assertEqual(country_register.get_root_register(), register)
        self.assertEqual(len(country_register.field_registry), 22)
        self.assertIs(register.field_registry, country_register.field_registry)
        self.assertIs(record_item, record.items[0])
        self.assertTrue(all(
            hasattr(record_item, attr)
            for attr in ['country', 'official_name', 'name', 'citizen_names']
        ))
        self.assertIsInstance(record.entry_number, int)
        self.assertIsInstance(record.entry_timestamp, datetime.datetime)
        self.assertIsInstance(record.items, list)
        self.assertIsNone(record_item.start_date)
        self.assertTrue(record_item.is_current)

    @unittest.skipUnless(os.environ.get('USE_INTERNET') == '1',
                         'set USE_INTERNET=1 environment variable to run test')
    def test_loading_from_internet(self):
        register = Register()
        self.assertGreater(len(register), 0)
        self.assertTrue(all(hasattr(record.item, register.register_info.register) for record in register))
        country_register = register.get_register('country')
        self.assertIn('GB', country_register)
        self.assertEqual(country_register.get_root_register(), register)
        record = register.get_record_using_curie('[country:GB]')
        self.assertEqual(record.key, 'GB')
