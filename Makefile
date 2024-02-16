.DEFAULT_GOAL:=help
SHELL:=/usr/bin/env bash
PYTHON_VERSION = $(shell head -1 .python-version)
PYTHON_VERSION_SHORT = $(shell head -1 .python-version | cut -d. -f 1-2)
PIP_PIPENV_VERSION = $(shell head -1 .pipenv-version)
PYTHON_DOCKER_NETWORK = "python-testing"
METRICS_FILE = "docs/metrics.md"
DOCKER = docker build --quiet \
	--file Dockerfile \
	--build-arg PYTHON_VERSION=$(PYTHON_VERSION) \
	--build-arg PIP_PIPENV_VERSION=$(PIP_PIPENV_VERSION) \
	--build-arg "user_id=${USER_ID}" \
	--build-arg "group_id=${GROUP_ID}" \
	--build-arg "home=${HOME}" \
	--build-arg "workdir=${PWD}" \
	--tag test-run:local . \
	&& docker run \
	--net $(PYTHON_DOCKER_NETWORK) \
	--interactive \
	--rm \
	--env "PYTHONWARNINGS=ignore:ResourceWarning" \
	--env "PYTHONPATH=${PWD}/src" \
	--volume "$(PWD):${PWD}:z" \
	--workdir "${PWD}" \
	test-run:local

GROUP_ID ?= $(shell id -g)
USER_ID ?= $(shell id -u)

.PHONY: help
help:
	@awk '/^#/{c=substr($$0,3);next}c&&/^[[:alpha:]][[:alnum:]_-]+:/{print substr($$1,1,index($$1,":")),c}1{c=0}' $(MAKEFILE_LIST) | column -s: -t
	@# Note that comments right before targets is used to auto-create the help section.

.PHONY: pyenv-install
# Install a fresh pyenv.
pyenv-install:
	@printf "\n=== Installing Pyenv ===\n"
	@git clone https://github.com/pyenv/pyenv.git ~/.pyenv
	@printf "Set up your shell as per:\n"
	@printf "https://github.com/pyenv/pyenv#set-up-your-shell-environment-for-pyenv\n"

.PHONY: pyenv-update
# Update an existing pyenv.
pyenv-update:
	@printf "\n=== Updating Pyenv ===\n"
	@pushd ~/.pyenv
	@git pull

.PHONY: create-piplockfile
# Create or update Pipfile.lock. Make sure to update any time changes are made to the Pipfile.
create-piplockfile:
	@printf "\n=== Locking Pipenv ===\n"
	@pipenv lock

.PHONY: create_docker_network
# Create the required Docker nework for the tests.
create_docker_network:
	@printf "\n=== Creating Docker network ===\n"
	@docker network create $(PYTHON_DOCKER_NETWORK)

.PHONY: check_docker_network
# Check that the required Docker networking exists.
check_docker_network:
	@printf "\n=== Checking Docker network ===\n"
	@if ! docker network inspect $(PYTHON_DOCKER_NETWORK) >/dev/null 2>&1; then printf "Required Docker networking for Python testing not found. See Make options to create it.\n" && exit 1; fi

.PHONY: test
# Run all the relevant tests.
test: black-fmt-test flake8-test unit-test integration-test code-analysis mypy-test md-fmt-test yaml-test docstr-coverage audit refurb metrics
	@printf "\n=== All tests completed! ===\n"

.PHONY: refurb
# A tool for refurbishing and modernizing Python codebases.
refurb:
	@printf "\n=== Running refurb ===\n"
	@$(DOCKER) pipenv run refurb --enable-all --python-version $(PYTHON_VERSION_SHORT) src

# I can't get bash command substition "<()" to work in Docker :(
# So have to create tmp file.
# "requirements" is only available in the latest pipenv
.PHONY: audit
# Check for vulnerabilities in the current dependencies per Pipfile.lock.
audit:
	@printf "\n=== Running Pip-audit ===\n"
	@$(DOCKER) pip install --upgrade pip pipenv > /dev/null 2>&1 && pipenv requirements > tmp_requirements_for_pip-audit_delete_me.txt
	@$(DOCKER) pipenv run pip-audit --requirement tmp_requirements_for_pip-audit_delete_me.txt
	@rm -f tmp_requirements_for_pip-audit_delete_me.txt

.PHONY: black-fmt
# Format with Black.
black-fmt:
	@printf "\n=== Applying Black formatting ===\n"
	@$(DOCKER) pipenv run black src/*py

.PHONY: black-fmt-test
# Test formatting with Black.
black-fmt-test:
	@printf "\n=== Testing Black formatting ===\n"
	@$(DOCKER) pipenv run black --check src/

.PHONY: mypy-test
# Run MyPy tests.
mypy-test:
	@printf "\n=== Running MyPy type checker ===\n"
	@$(DOCKER) pipenv run mypy --show-error-codes --namespace-packages --explicit-package-bases --strict src

.PHONY: flake8-test
# Run Flake8 tests.
flake8-test:
	@printf "\n=== Running Flake8 style guide ===\n"
	@$(DOCKER) pipenv run flake8 --exclude tests

.PHONY: unit-test
# Run Python unit tests.
unit-test:
	@printf "\n=== Running all unit tests ===\n"
	@$(DOCKER) pipenv run pytest -s\
		--cov=src \
		--cov-report "term-missing:skip-covered" \
		--cov-fail-under=100 \
		--no-cov-on-fail \
		--no-header \
		-vvv \
	  tests/unit*

define docker_cleanup
	printf "Cleaning up Docker container ...\n"; \
	docker stop $(DOCKER_ID) &> /dev/null || true; \
	docker rm $(DOCKER_ID) &> /dev/null || true
endef

.PHONY: integration-test
# Run Python integration tests.
integration-test: check_docker_network
	@printf "\n=== Running all integration tests ===\n"
	@printf "Starting Docker container ...\n"
	$(eval DOCKER_ID := $(shell ./tests/start_long_running_docker.py))
	@if [[ $$(echo '$(DOCKER_ID)' | wc -c) -ge 14 ]]; then printf 'Could not start docker:\n$(DOCKER_ID)' && exit 1; fi
	@printf "Starting integration tests ...\n"
	@$(DOCKER) pipenv run pytest -s --no-header -vvv tests/integration* && $(call docker_cleanup) || $$($(call docker_cleanup); exit 1)

.PHONY: code-analysis
# Run static code analysis with Bandit.
code-analysis:
	@printf "\n=== Running Bandit code analysis ===\n"
	@$(DOCKER) pipenv run bandit -r src

.PHONY: md-fmt-test
# Test Markdown formatting with Remark linting.
md-fmt-test:
	@printf "\n=== Running Remark Markdown linting ===\n"
	@docker pull -q zemanlx/remark-lint:latest
	@docker run --rm -i -v $(PWD):/lint/input:ro zemanlx/remark-lint --frail .

.PHONY: yaml-test
# Test YAML files with Yaml linting.
yaml-test:
	@printf "\n=== Running YAML linting ===\n"
	@$(DOCKER) pipenv run yamllint -s config/*.yaml

.PHONY: api-docs
# Auto-generate API docs with Sphinx.
api-docs:
	@printf "\n=== Building HTML documentation ===\n"
	@$(DOCKER) pipenv run sphinx-build -M html api_docs/ api_docs/_build/

.PHONY: docstr-coverage
# Docstring coverage test.
docstr-coverage:
	@printf "\n=== Running docstring coverage test ===\n"
	@$(DOCKER) pipenv run docstr-coverage src

.PHONY: metrics
# Generate metrics.
metrics:
	@printf "\n=== Generating metrics ===\n"
	@printf "# Metrics\n\n" > $(METRICS_FILE)
	@printf "## Cyclomatic Complexity and Maintainability Index\n\n" >> $(METRICS_FILE)
	@printf "<!--lint disable-->\n" >> $(METRICS_FILE)
	@$(DOCKER) pipenv run radon cc -a --md src >> $(METRICS_FILE)
	@printf "<!--lint enable-->\n\n" >> $(METRICS_FILE)
	@sed -i 's|__|\\_\\\_|g' $(METRICS_FILE)
	@printf "## Raw Metrics\n\n" >> $(METRICS_FILE)
	@printf '```bash\n' >> $(METRICS_FILE)
	@$(DOCKER) pipenv run radon raw -s src | awk '/** Total **/,0' >> $(METRICS_FILE)
	@printf '```\n' >> $(METRICS_FILE)

.PHONY: run
# Run the program. You must pass in the command to run in single quotes.:Example:make run command='my_command --with args'.
run: check_input
	@printf "\n=== Running application ===\n"
	@$(DOCKER) pipenv run python $(subst ',,$(command))

.PHONY: profile
# Profile the code. You must pass in the command to profile in single quotes.:Example:make profile command='my_command --with args'.
profile: check_input
	@printf "\n=== Profile ===\n"
	@$(DOCKER) pipenv run python -m cProfile -o running_profile.pstats $(subst ',,$(command))
	@$(DOCKER) pipenv run gprof2dot --node-thres=1 --format=pstats running_profile.pstats --output=running_profile.pstats.dot
	@$(DOCKER) dot -Tpng running_profile.pstats.dot -o running_profile.png
	@rm running_profile.pstats.dot

.PHONY: check_input
check_input:
	@for var in command ; do \
		eval test -n \"\$$$$var\" \
		|| { echo "The '$$var' arguments is required. See 'make help' for further information."; exit 1; }; \
	done
