Development and releases
========================

Set up a checkout
-----------------

.. code-block:: console

   git clone https://github.com/gijzelaerr/s7commplus.git
   cd s7commplus
   python -m venv .venv
   . .venv/bin/activate
   python -m pip install -e '.[test,docs]' build twine

Run the complete checks
-----------------------

.. code-block:: console

   pytest
   mypy s7commplus
   ruff check s7commplus tests
   ruff format --check s7commplus tests
   sphinx-build -W --keep-going -b html docs docs/_build/html
   python -m build
   twine check dist/*
   pre-commit run --all-files

Real-PLC tests are opt-in and require an explicitly selected, disposable test
DB. Follow :doc:`real-plc-testing` for TLS configuration, the safe runner, and
sanitized evidence collection.

Build the documentation
-----------------------

The same warning-strict Sphinx command runs in GitHub Actions and Read the
Docs. Open ``docs/_build/html/index.html`` after a local build.

Release process
---------------

The package version is declared in ``pyproject.toml``. A GitHub Release tag
must match it exactly with a ``v`` prefix; version ``0.1.0`` therefore uses tag
``v0.1.0``. The release workflow reruns tests, typing, lint, documentation, and
distribution validation before publishing through PyPI trusted publishing.

Publishing requires a protected GitHub environment named ``pypi`` and a PyPI
trusted publisher bound to ``gijzelaerr/s7commplus``, ``release.yml``, and that
environment. No long-lived PyPI token is stored in GitHub.
