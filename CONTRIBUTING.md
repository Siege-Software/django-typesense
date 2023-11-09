## Contribution

django-typesense’s git main branch should always be stable, production-ready & passing all tests.

### Setting up the project

```sh
# clone the repo
git clone https://github.com/Siege-Software/django-typesense.git
git checkout -b <your_branch_name> main

# Set up virtual environment
python3.8 -m venv venv
source venv/bin/activate

pip install -r requirements-dev.txt

# Enable automatic pre-commit hooks
pre-commit install
```

### Running Tests

```sh
python runtests.py
```

### Building the package

```sh
python -m build
```

### Installing the package from build

```sh
pip install path/to/django_typesense-0.0.1.tar.gz
```
