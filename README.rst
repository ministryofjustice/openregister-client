Open Registers Client
=====================

**DEPRECATED**

GOV.UK Registers were discontinued in March 2021 so this client is no longer being developed or updated.

Usage
-----

``openregister_client.registers.OpenRegister`` is the base class that accesses a single register and ignores field data typing information.
``openregister_client.registers.Register`` and ``openregister_client.registers.AlphaRegister`` use
the "register" register to discover available registers and the field data types their items should contain.
Records, entries and items (the actual data contained in records) returned are ``dict`` subclasses that provide typed attributes to access the register data more easily.

Currently, only compatible with Python 3.6+.

Install using ``pip install openregister-client``.

Usage samples:

.. code-block:: python

    # direct register usage; field types will not have correct types, but data can be loaded more simply
    from openregister_client.registers import OpenRegister

    country_register = OpenRegister(name='country')
    country_record = country_register.get_record('GB')
    print('The official name for GB is %s' % country_record.item.official_name)
    if not country_record.item.is_current:
        print('This country is not currently recognised')

    # using register auto-discovery to process fields and datatypes
    from openregister_client.registers import Register

    register = Register()
    territory_register = register.get_register('territory')
    territory_items = sorted(map(lambda record: record.item, territory_register.get_records()), key=lambda item: item.territory)
    for territory in territory_items:
        print('The official name for territory %s is %s' % (territory.territory, territory.official_name))

    # make a Django model class; works best when using auto-discovery
    from openregister_client.django_compat.model_factory import ModelFactory
    from openregister_client.registers import Register

    country_register = Register().get_register('country')
    with open('models.py', 'wt') as f:
        f.write(ModelFactory(country_register).get_model_code())

    # an API key can be provided when instantiating a register class
    country_register = OpenRegister(name='country', api_key='YOUR API KEY')

Caching is not implemented. Users of the library can store results of queries or subclass ``OpenRegister.request`` to add caching.

Consuming non-json input formats is not supported and probably not necessary.

Development
-----------

.. image:: https://github.com/ministryofjustice/openregister-client/workflows/Run%20tests/badge.svg?branch=master
    :target: https://github.com/ministryofjustice/openregister-client/actions


Use ``python setup.py test`` to run all tests.

Distribute a new version by updating the ``VERSION`` tuple in ``openregister_client/__init__.py`` and
publishing a release in `GitHub`_ (this triggers a GitHub Actions workflow to automatically upload it).
Alternatively, run ``python setup.py sdist bdist_wheel upload`` locally.

To-do
-----

* Do not paginate past the end since numbers of entries and records are known
* Perhaps lower minimum Python version to 3.4 or 3.5; use ``typing`` module

References
----------

* https://www.registers.service.gov.uk/ (no longer available)
* https://docs.registers.service.gov.uk/ (no longer available)
* http://openregister.github.io/specification/ (no longer available; was possibly outdated before)
* http://open-registers-docs.readthedocs.io/en/latest/ (deleted)

Copyright
---------

Copyright (C) 2020 HM Government (Ministry of Justice Digital & Technology).
See LICENSE.txt for further details.

.. _GitHub: https://github.com/ministryofjustice/openregister-client
