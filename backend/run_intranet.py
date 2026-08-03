import os
import socket


def _get_port():
    try:
        port = int(os.environ.get('INTRANET_PORT', '8088'))
    except ValueError as error:
        raise SystemExit('INTRANET_PORT must be an integer.') from error
    if not 1 <= port <= 65535:
        raise SystemExit('INTRANET_PORT must be between 1 and 65535.')
    if port == 8090:
        raise SystemExit('Port 8090 is reserved for the existing service.')
    return port


def _detect_lan_ip():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(('172.16.50.20', 3306))
        return probe.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        probe.close()


PORT = _get_port()
PUBLIC_URL = os.environ.get('INTRANET_PUBLIC_URL') or (
    f'http://{_detect_lan_ip()}:{PORT}'
)
os.environ['SERVE_FRONTEND'] = '1'
os.environ['PASSWORD_RESET_FRONTEND_URL'] = PUBLIC_URL.rstrip('/')

from app import create_app

app = create_app()


if __name__ == '__main__':
    try:
        from waitress import serve
    except ImportError as error:
        raise SystemExit(
            'waitress is required; install backend/requirements.txt first.'
        ) from error

    print(f'Serving intranet site on {PUBLIC_URL} (waitress, 16 threads)')
    serve(app, host='0.0.0.0', port=PORT, threads=16)
