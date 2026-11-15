"""Production entry point: gunicorn serves `deploy.wsgi:app` (see deploy/Dockerfile).

`python main.py` stays the way to run the backend locally. Here the data source
comes from the BACKEND_DATA environment variable ("mock" or "database"), the
same variable main.py reads.

Run locally, from backend/:   gunicorn --bind :8080 deploy.wsgi:app
"""

from main import create_app
from src import config
from src.database import open_database

app = create_app(open_database(config.DATA))
