"""Local config; never commit production secrets."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = ROOT / '.data'
DATA.mkdir(exist_ok=True)

def db_url(name: str) -> str:
    return os.environ.get(f'{name.upper()}_DATABASE_URL', f'sqlite:///{DATA / (name + ".db")}')

def service_url(name: str) -> str:
    ports = {'auth':8001, 'stores':8002, 'catalog':8003, 'inventory':8004, 'orders':8005, 'delivery':8006}
    return os.environ.get(f'{name.upper()}_SERVICE_URL', f'http://127.0.0.1:{ports[name]}')

JWT_SECRET = os.environ.get('JWT_SECRET', 'local-dev-only-secret-change-before-deploying-2026')
INTERNAL_KEY = os.environ.get('INTERNAL_API_KEY', 'local-internal-dev-secret-change-before-deploying-2026')
