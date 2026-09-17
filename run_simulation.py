"""
Drosophila melanogaster - 3D Connectome Simulation Server
=========================================================
Launches local web server for WebGL 3D simulation with Google Connectome dynamics,
env.glb plane environment, and WASD + PointerLock mouse controls.
"""

import http.server
import socketserver
import webbrowser
import os
import sys

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Enable CORS and caching headers for 3D glb assets
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

def run():
    os.chdir(DIRECTORY)
    # Find free port if 8000 is occupied
    port = PORT
    server = None
    for p in range(PORT, PORT + 20):
        try:
            server = socketserver.TCPServer(("", p), Handler)
            port = p
            break
        except OSError:
            continue

    if not server:
        print(">> Error: Could not find an available port.")
        sys.exit(1)

    url = f"http://localhost:{port}/index.html"
    print("=" * 65)
    print("  DROSOPHILA MELANOGASTER - 3D CONNECTOME SIMULATION SERVER")
    print("=" * 65)
    print(f">> Server running at: {url}")
    print(f">> Serving directory: {DIRECTORY}")
    print(">> Controls:")
    print("   [W / S]       : Forward / Backward (DNb01 / MDN)")
    print("   [A / D]       : Steering Left / Right (DNa01 / DNa02)")
    print("   [Shift]       : Speed Boost")
    print("   [Space]       : Giant Fiber Escape Jump (DNp01)")
    print("   [Mouse]       : Orbit Camera Look")
    print("   [Esc]         : Lock / Unlock Mouse Cursor")
    print("=" * 65)
    print(">> Launching browser...")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n>> Server stopped.")
        server.server_close()

if __name__ == "__main__":
    run()
