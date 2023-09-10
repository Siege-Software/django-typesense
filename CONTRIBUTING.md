## Contribution
django-typesense’s git main branch should always be stable, production-ready & passing all tests.

### Setting up the project
```
# clone the repo
git clone https://gitlab.com/siege-software/packages/django_typesense.git
git checkout -b <your_branch_name> stable/1.x.x

# Set up virtual environment
python3.8 -m venv venv
source venv/bin/activate

pip install -r requirements-dev.txt

# Enable automatic pre-commit hooks
pre-commit install
```

### Running Tests
```
cd tests
pytest .
```

### Building the package
`python -m build`

### Installing the package from build
` pip install path/to/django_typesense-0.0.1.tar.gz`
