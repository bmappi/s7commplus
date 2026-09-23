Development and releases
========================

Set up a checkout
-----------------

This source-checkout workflow is for developing and testing ``s7commplus``.
Applications should instead install the stable release from `PyPI
<https://pypi.org/project/s7commplus/>`_ as described in
:doc:`getting-started`.

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

Session authentication research
-------------------------------

The checkout includes analysis tools for the HarpoS7-derived authentication
transforms. They regenerate exact Boolean models, print recovered gate
formulas, decompile arithmetic tape dependencies, and benchmark model costs:

.. code-block:: console

   python -m tools.recover_monolith5_gates --formula 0
   python -m tools.recover_monolith7_full --verify tools/monolith7_full_model.json
   python -m tools.decompile_transform12 --phase2 --output-slot 27
   python -m tools.benchmark_session_auth_models

The tools run from the checkout and do not replace the packaged runtime.
Read the `analysis and verification boundary
<https://github.com/gijzelaerr/s7commplus/blob/master/s7commplus/session_auth/ARCHITECTURE.md>`_
and `model benchmark findings
<https://github.com/gijzelaerr/s7commplus/blob/master/s7commplus/session_auth/MODEL_BENCHMARKS.md>`_
before using a recovered evaluator as an implementation.

Release process
---------------

The package version is declared in ``pyproject.toml``. A GitHub Release tag
must match it exactly with a ``v`` prefix; version ``0.1.0`` therefore uses tag
``v0.1.0``. The release workflow reruns tests, typing, lint, documentation, and
distribution validation before publishing through PyPI trusted publishing.

Publishing requires a protected GitHub environment named ``pypi`` and a PyPI
trusted publisher bound to ``gijzelaerr/s7commplus``, ``release.yml``, and that
environment. No long-lived PyPI token is stored in GitHub.
