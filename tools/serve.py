"""Serves a folder over HTTPS on every interface, for trying the page from another computer."""
import functools
import http.server
import ssl
import sys

root, port, cert, key = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


httpd = http.server.ThreadingHTTPServer(('0.0.0.0', port), functools.partial(Handler, directory=root))
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(cert, key)
httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
print('serving', root, 'on', port, flush=True)
httpd.serve_forever()
