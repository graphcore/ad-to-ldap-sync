[![black](https://img.shields.io/badge/black-pass-brightgreen)](https://github.com/psf/black)
[![mypy](https://img.shields.io/badge/mypy-pass-brightgreen)](http://mypy-lang.org/)
[![flake8](https://img.shields.io/badge/flake8-pass-brightgreen)](https://flake8.pycqa.org/en/latest/)
[![unit-test](https://img.shields.io/badge/unit%20test-pass-brightgreen)](tests/)
[![integration-test](https://img.shields.io/badge/integration%20test-pass-brightgreen)](tests/)
[![code-analysis](https://img.shields.io/badge/bandit-pass-brightgreen)](https://github.com/PyCQA/bandit)
[![markdown-lint](https://img.shields.io/badge/markdown-pass-brightgreen)](https://github.com/zemanlx/remark-lint)
[![yaml-lint](https://img.shields.io/badge/YAML%20lint-pass-brightgreen)](https://github.com/adrienverge/yamllint)
[![docstr-coverage](https://img.shields.io/badge/docstring-pass-brightgreen)](api_docs/_build/html/index.html)

# MS AD to OpenLDAP sync tooling

This tool is used to synchronize groups and users between MS AD and OpenLDAP.
In general it is run via a cron job, but can also be used on an ad-hoc basis.

## Release process

-   Make a new branch and merge your changes to it
    - Make sure your changes in your feature branch are checked in
    - `make test` Make sure all tests pass (you might need `-i` if you have outstanding test failures)
    - In gitlab, create a merge request from your feature branch to main
        - Make sure you squash commits to reduce the amount of clutter in the comments on main
    - Create your new release branch from main
        - `git branch` to make sure you are on "main"
        - `git checkout main` to swap to main if you are not there        - `git pull` to ensure you pull your earlier merge from the feature branch
        - `git checkout -b v1.0` to create and switch to the new feature branch
        - `git push --set-upstream origin v1.0` to push your new release branch to the git server
-   Deploy your release to the production server
    - `ssh server.name` to log in to the LDAP master
    - `sudo -u service_user -i` to become the service account user
    - Disable the existing sync scripts
        - `crontab -e` and comment out (with `i` and `Esc`) with a `#` at the start of each line, both cron jobs (one for user_sync, and one for group_sync)
        - `:wq` to save and quit the cron editor
    - Update the git repo to your new release version
        - `cd ad-to-ldap-sync/` to change to the git repo
        - `git pull` to get the new branch names
        - `git checkout v1.0` to change to the new release branch
        - You are now using the new feature branch
    - Update config file if necessary to include and new config options
        - `diff -i --side-by-side --suppress-common-lines config/config-template.yaml config/config.yaml | grep -Ev 'bind_user|bind_pass|ca_certs_file'`
    - Make sure that python has all the requirements installed
        - `pip install -r requirements.txt`
    - Update the commented out cron lines to take account of any new command line options
    - Run a manual test of user_sync and group_sync in noop mode to verify they run as expected. Look for unexpected errors
        - `/home/service_user/.pyenv/versions/3.10.1/bin/python /home/service_user/ad-to-ldap-sync/ad_to_ldap_sync.py group_sync --config_file /home/service_user/ad-to-ldap-sync/config/config.yaml --console error` for group_sync
        - `/home/service_user/.pyenv/versions/3.10.1/bin/python /home/service_user/ad-to-ldap-sync/ad_to_ldap_sync.py user_sync --config_file /home/service_user/ad-to-ldap-sync/config/config.yaml --console error` for user_sync
        - Check the monitoring log files both have "True" in them
            - `for i in *monitoring.log; do echo $(cat $i); done`
        - Look for errors or warnings in either of the script log files
            - `less group_sync_ad-to-ldap-sync.log` for group sync
            - `less user_sync_ad-to-ldap-sync.log` for user sync
    - Reinstate the cron job so that the scripts will run automatically
        - `crontab -e` and remove the two commented out (with `i` and `Esc`) lines by removing `#` from the start (one for user_sync, and one for group_sync)
        - `:wq` to save and quit the cron editor
    - Release is completed. Bask in the glorious admiration of your colleagues.


## Configuration details

[Configuration details](docs/configuration-details.md)

## Auto-generated API documentation

[API documentation](api_docs/_build/html/index.html)

## Metrics

[Metrics](docs/metrics.md)

## Development

-   Use NumPy/SciPy [Docstrings](https://numpydoc.readthedocs.io/en/latest/format.html)
-   Use [Sphinx](https://www.sphinx-doc.org/en/master/)

### Breakpoints

At any point in the code you can add `breakpoint()` to add a breakpoint.
In addition to that, set the environment variable `$PYTHONBREAKPOINT = 'web_pdb.set_trace'`.
This will then launch Pdb on port 5555 (`web-pdb` required). Use your browser of
preference to open it and step through.

### Sphinx setup

-   Create the basic configuration:

```bash
mkdir api_docs && pushd api_docs
sphinx-quickstart \
--no-sep \
--project "MS AD <-> OpenLDAP sync" \
--author "Peter & Martinus" \
--ext-autodoc \
--ext-coverage \
--extensions sphinx.ext.napoleon \
--makefile \
--no-batchfile \
--language en \
--release "v1"

sphinx-apidoc -o . ../src
popd
```

-   Install the `autodocsumm` module:

```bash
pip install autodocsumm
```

-   Set the path correctly:

```bash
sed -i '1 i\
import os\
import sys\
\
sys.path.insert(0, os.path.abspath(".."))' api_docs/conf.py
```

-   Set the autodoc options

```bash
sed -i '/Options for HTML output/i\
autodoc_default_options = {\
    "autosummary": True,\
    "members": True,\
    "undoc-members": True,\
    "private-members": True,\
}' api_docs/conf.py
```

-   Set the theme as the default is ....

```bash
sed -i 's/alabaster/classic/' api_docs/conf.py
```

-   Set the side bar and body width:

```bash
echo 'html_theme_options = {"sidebarwidth": 400, "body_max_width": "none"}' >> api_docs/conf.py
```

-   Ignore the `modules.rst` file

```bash
sed -i '1 i\:orphan:\' api_docs/modules.rst
```

### Docstring coverage

```bash
pip install docstr-coverage
```

## Profiling

If you want to see where things are slow:

```bash
python -m cProfile -o output.pstats ad_to_ldap_sync.py --conf config/config.yaml --exc config/exceptions.yaml --cons debug --count config/country_control.yaml
```

And to then graph it use [gprof2dot](https://github.com/jrfonseca/gprof2dot):

```bash
gprof2dot -f pstats output.pstats | dot -Tpng -o output.png
```

## Creating a compiled executeable

In order to easily share the program over a wide set of systems and not worry
about either containers or Python versions and module, you can compile the
entire program into a single binary.

For further information see [PyInstaller](https://pyinstaller.org/en/stable/usage.html)

*NOTE:* As of this writing, UPX is not used on Linux.

### Ensure you have shared libraries

If you use `pyenv`:

```bash
env PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.10.1
```

### Create the binary

```bash
pyinstaller --clean -F ad-to-ldap-sync.py
```

The binary will be located with the same name in the `dist/` directory.

## TODO

### New feature(s)

-   Email user with link to Password reset page (in check_change) (Future)

-   Cope with large LDAP queries, and pagination (Future)

-   If the AD object in a group is itself a group, recursively descend and build
    full member list. (soonish)

-   Set recursion limit based on len(called_groups) and config file in
    _flatten_nested_group

-   Investigate below 'md4' as it is a broken algorythm:
    https://cwe.mitre.org/data/definitions/327.html

-   Need integration testing for adding multiple users at once.

-   Duplicate duplicate duplicate code between user and group sync

-   Clean up unit tests so they don't leave log files behind.

-   Ensure 100% code coverage for unit tests.

-   Create integration tests for user_sync.

### Testing

-   We would benefit from AD "test users" instead of named ones. This would
    make testing cleaner and safer.

-   Configure OpenLDAP Docker container for integration tests.

-   Run through all methods and compare with unit-tests, verify we do all the
    things
