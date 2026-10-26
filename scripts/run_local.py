"""Launch six FastAPI services for local development (no Docker yet)."""
import subprocess
import sys
import signal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PORTS={'auth':8001,'stores':8002,'catalog':8003,'inventory':8004,'orders':8005,'delivery':8006}

def main():
    processes=[]
    try:
        for name,port in PORTS.items():
            p=subprocess.Popen([sys.executable,'-m','uvicorn',f'services.{name}.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT)
            processes.append(p)
            print(f'Started {name:12} http://127.0.0.1:{port}/docs',flush=True)
        print('APIs started. In another terminal: cd frontend && npm install && npm run dev',flush=True)
        while all(p.poll() is None for p in processes):
            processes[0].wait(timeout=0.5)
    except KeyboardInterrupt:pass
    except subprocess.TimeoutExpired:main_wait(processes)
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill()

def main_wait(processes):
    try:
        while all(p.poll() is None for p in processes):
            import time; time.sleep(.5)
    except KeyboardInterrupt:pass

if __name__=='__main__':main()
