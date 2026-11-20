"""Verify the source and frozen application against a temporary PostgreSQL cluster."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def wait_http(server, port):
    for _ in range(60):
        if server.poll() is not None:
            break
        try:
            with urlopen(f'http://127.0.0.1:{port}/login', timeout=1) as response:
                if response.status == 200 and b'name="clave"' in response.read():
                    return
        except (TimeoutError, URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError('El formulario de inicio de sesión no respondió desde el paquete.')


def main(executable):
    with tempfile.TemporaryDirectory(prefix='agrotrack-ci-') as directory:
        cluster = Path(directory) / 'pgdata'
        port = free_port()
        web_port = free_port()
        while web_port == port:
            web_port = free_port()
        subprocess.run(['initdb', '-D', cluster, '-U', 'postgres', '-A', 'trust', '-E', 'UTF8',
                        '--no-locale'], check=True)
        server = None
        try:
            subprocess.run(['pg_ctl', '-D', cluster, '-l', Path(directory) / 'postgres.log',
                            '-o', f'-h 127.0.0.1 -p {port} -c unix_socket_directories=',
                            '-w', 'start'], check=True)
            env = dict(os.environ, POSTGRES_ADMIN_DSN=f'host=127.0.0.1 port={port} user=postgres dbname=postgres',
                       AGROTRACK_DATA_DIR=directory, AGROTRACK_TEST_REPORT_DIR=directory,
                       PORT=str(web_port), PYTHONUTF8='1')
            subprocess.run([executable, '--setup'], env=env, check=True)
            subprocess.run([executable, '--check'], env=env, check=True)
            for test in ('verificar.py', 'verificar_admin.py'):
                subprocess.run([sys.executable, test], env=env, check=True)
            env.pop('POSTGRES_ADMIN_DSN')
            server = subprocess.Popen([executable], env=env)
            wait_http(server, web_port)
            with urlopen(f'http://127.0.0.1:{web_port}/static/style.css', timeout=3) as response:
                if response.status != 200 or 'text/css' not in response.headers.get('Content-Type', ''):
                    raise RuntimeError('No se encontró la hoja de estilos empaquetada.')
            print('Paquete verificado por HTTP con PostgreSQL real.')
        finally:
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
            subprocess.run(['pg_ctl', '-D', cluster, '-m', 'fast', '-w', 'stop'], check=False)


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
