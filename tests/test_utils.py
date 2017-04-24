import datetime
import unittest

from openregister_client.util import Year, YearMonth, camel_case, markdown, utc
from openregister_client.util import parse_curie, parse_datetime, parse_item_hash, parse_text, parse_timestamp


class UtilTestCase(unittest.TestCase):
    def test_datetime_parsing(self):
        self.assertEqual(parse_datetime('2017-02-02'), datetime.date(2017, 2, 2))
        self.assertEqual(parse_datetime('2017-02-02T12'), datetime.datetime(2017, 2, 2, 12, tzinfo=utc))
        self.assertEqual(parse_datetime('2017-02-02T12:30'), datetime.datetime(2017, 2, 2, 12, 30, tzinfo=utc))
        self.assertEqual(parse_datetime('2017-02-02T12:30:15'), datetime.datetime(2017, 2, 2, 12, 30, 15, tzinfo=utc))
        self.assertEqual(parse_datetime('2017-02-02T12:30:15Z'), datetime.datetime(2017, 2, 2, 12, 30, 15, tzinfo=utc))
        self.assertEqual(parse_datetime('2017'), Year(2017))
        self.assertEqual(parse_datetime('2017-02'), YearMonth(2017, 2))
        self.assertEqual(str(parse_datetime('2017-02')), '2017-02')

        with self.assertRaises(ValueError):
            parse_datetime(None)
        with self.assertRaises(ValueError):
            parse_datetime('2017-02-30')
        with self.assertRaises(ValueError):
            parse_datetime('2017-02-30T12:00:00')

    def test_item_hash_parsing(self):
        item = parse_item_hash('sha-256:61c1403c4493fd7dffcdd122c62e46e22cfb64ef68f057a0b5d7d753b9237689')
        self.assertEqual(item, 'sha-256:61c1403c4493fd7dffcdd122c62e46e22cfb64ef68f057a0b5d7d753b9237689')
        self.assertEqual(item.algorithm, 'sha-256')
        self.assertEqual(item.value, '61c1403c4493fd7dffcdd122c62e46e22cfb64ef68f057a0b5d7d753b9237689')

        with self.assertRaises(ValueError):
            parse_item_hash(None)
        with self.assertRaises(ValueError):
            parse_item_hash('')
        with self.assertRaises(ValueError):
            parse_item_hash('sha-256')
        with self.assertRaises(ValueError):
            parse_item_hash('sha-256:61c1403c4493fd7dffcdd122c62e46e22cfb64ef68f057a0b5d7d753b923768')
        with self.assertRaises(ValueError):
            parse_item_hash('md5:0dbf4d1543bf511ef9a99a6e64d1325a')

    def test_timestamp_parsing(self):
        self.assertEqual(parse_timestamp('2017-02-02T12:30:15Z'), datetime.datetime(2017, 2, 2, 12, 30, 15, tzinfo=utc))

        with self.assertRaises(ValueError):
            parse_timestamp(None)
        with self.assertRaises(ValueError):
            parse_timestamp('2017-02-02T12:30:15')
        with self.assertRaises(ValueError):
            parse_timestamp('2017-02-02')
        with self.assertRaises(ValueError):
            parse_timestamp('2017')

    @unittest.skipUnless(markdown, 'Markdown support is not installed')
    def test_text_datatype_support(self):
        self.assertEqual(parse_text(None).html, '')
        self.assertEqual(parse_text('').html, '')
        self.assertEqual(parse_text('Ministry of Justice').html, '<p>Ministry of Justice</p>')
        self.assertEqual(parse_text('*Ministry* of Justice').html, '<p><em>Ministry</em> of Justice</p>')

    def test_camel_case(self):
        self.assertEqual(camel_case('register'), 'Register')
        self.assertEqual(camel_case('country-register'), 'CountryRegister')
        self.assertEqual(camel_case('COUNTRY-REGISTER'), 'CountryRegister')
        self.assertEqual(camel_case('CountryRegister'), 'Countryregister')

    def test_curie(self):
        curie = parse_curie('country:GB')
        self.assertEqual(curie.prefix, 'country')
        self.assertEqual(curie.reference, 'GB')
        self.assertEqual(curie.safe_format, '[country:GB]')
        curie = parse_curie('[country:FR]')
        self.assertEqual(curie.prefix, 'country')
        self.assertEqual(curie.reference, 'FR')
        self.assertEqual(str(curie), 'country:FR')
        self.assertEqual(curie.safe_format, '[country:FR]')

        with self.assertRaises(ValueError):
            parse_curie(None)
        with self.assertRaises(ValueError):
            parse_curie('')
        with self.assertRaises(ValueError):
            parse_curie('country:GB:Wales')
