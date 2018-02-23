Open Registers Client
=====================

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

Caching is not implemented. Users of the library can store results of queries or subclass ``OpenRegister.request`` to add caching.

Consuming non-json input formats is not supported and probably not necessary.

Development
-----------

.. image:: https://travis-ci.org/ministryofjustice/openregister-client.svg?branch=master
    :target: https://travis-ci.org/ministryofjustice/openregister-client


Please report bugs and open pull requests on `GitHub`_.

Use ``python setup.py test`` to run all tests.

Distribute a new version by updating the ``VERSION`` tuple in ``openregister_client/__init__.py`` and run ``python setup.py sdist bdist_wheel upload``.

To-do
-----

* Do not paginate past the end since numbers of entries and records are known
* Perhaps lower minimum Python version to 3.4 or 3.5; use ``typing`` module

References
----------

* http://www.openregister.org/
* https://registers.cloudapps.digital/
* https://registers-docs.cloudapps.digital/
* http://openregister.github.io/specification/ (outdated)
* http://open-registers-docs.readthedocs.io/en/latest/ (deleted)

Copyright
---------

Copyright (C) 2018 HM Government (Ministry of Justice Digital Services).
See LICENSE.txt for further details.

.. _GitHub: https://github.com/ministryofjustice/openregister-client
