"""rec_server.py <out_dir> [port] — receives view3d's recorder frames (POST /frame?n=..&...) and writes out_dir/frames/NNNNNN.jpg
plus one JSON line of metadata per frame in out_dir/meta.jsonl. CORS open (the page is served by localhost:8765)."""
import sys, os, json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
OUT = sys.argv[1]; PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8777
os.makedirs(os.path.join(OUT, 'frames'), exist_ok=True)
META = open(os.path.join(OUT, 'meta.jsonl'), 'a')
class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()
    def do_GET(self):
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b'ok')
    def do_POST(self):
        u = urlparse(self.path); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        if u.path == '/frame':
            n = int(q['n']); open(os.path.join(OUT, 'frames', '%06d.jpg' % n), 'wb').write(body)
            META.write(json.dumps(q) + '\n'); META.flush()
        self.send_response(200); self._cors(); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a): pass
ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
