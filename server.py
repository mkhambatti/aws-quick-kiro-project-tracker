"""Local training server. Python standard library only."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json
from decision import evaluate
ROOT = Path(__file__).resolve().parent
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/':
            body = (ROOT/'index.html').read_bytes(); kind='text/html; charset=utf-8'
        elif url.path == '/api/report':
            snapshot = parse_qs(url.query).get('snapshot',['a'])[0]
            if snapshot not in ('a','b'):
                self.send_error(400,'Use snapshot a or b'); return
            rows = json.loads((ROOT/f'data/snapshot_{snapshot}.json').read_text())
            body = json.dumps([dict(row,decision=evaluate(row)) for row in rows]).encode()
            kind='application/json'
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type',kind)
        self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
if __name__ == '__main__':
    print('Open http://127.0.0.1:8766', flush=True)
    try: HTTPServer(('127.0.0.1',8766),Handler).serve_forever()
    except KeyboardInterrupt: print('Stopped.')
