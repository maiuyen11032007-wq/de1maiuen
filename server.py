import http.server
import socketserver
import json
import os
import urllib.parse
from agent.workflow_engine import MinhAnWorkflowEngine, load_json, save_json, PRODUCTS_FILE, PIPELINE_FILE, SALES_FILE, POLICIES_FILE

PORT = 8000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

engine = MinhAnWorkflowEngine()

class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

class MinhAnApiHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(STATIC_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/api/products":
            self._send_json(load_json(PRODUCTS_FILE, []))
            return

        if path == "/api/sales_team":
            self._send_json(load_json(SALES_FILE, []))
            return

        if path == "/api/policies":
            self._send_json(load_json(POLICIES_FILE, {}))
            return

        if path == "/api/pipeline":
            self._send_json(load_json(PIPELINE_FILE, []))
            return

        # Fallback to static files
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            req_data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            req_data = {}

        if path == "/api/process":
            raw_text = req_data.get("raw_text", "").strip()
            existing_opp_id = req_data.get("existing_opp_id")
            override_fields = req_data.get("override_fields")
            if not raw_text and not override_fields:
                self._send_json({"error": "Văn bản yêu cầu không được để trống"}, status=400)
                return
            result = engine.process_request(raw_text, existing_opp_id=existing_opp_id, override_fields=override_fields)
            self._send_json(result)
            return

        if path == "/api/clarify_reply":
            opp_id = req_data.get("opp_id")
            reply_text = req_data.get("reply_text", "").strip()
            extra_fields = req_data.get("extra_fields")
            res = engine.submit_customer_clarification(opp_id, reply_text, extra_fields)
            self._send_json(res)
            return

        if path == "/api/approve":
            opp_id = req_data.get("opp_id")
            notes = req_data.get("notes", "Đã duyệt theo thẩm quyền")
            approved_discount = req_data.get("approved_discount")
            res = engine.approve_opportunity(opp_id, notes, approved_discount=approved_discount)
            self._send_json(res)
            return

        if path == "/api/send_endtrack":
            opp_id = req_data.get("opp_id")
            res = engine.mark_sent_endtrack(opp_id)
            self._send_json(res)
            return

        if path == "/api/products/update":
            sku = req_data.get("sku")
            new_stock = req_data.get("available_stock")
            new_price = req_data.get("current_price")

            products = load_json(PRODUCTS_FILE, [])
            updated = False
            for p in products:
                if p["sku"] == sku:
                    if new_stock is not None:
                        p["available_stock"] = int(new_stock)
                    if new_price is not None:
                        p["current_price"] = float(new_price)
                    updated = True
                    break

            if updated:
                save_json(PRODUCTS_FILE, products)
                engine.reload_data()
                self._send_json({"success": True, "message": f"Đã cập nhật SKU {sku}"})
            else:
                self._send_json({"success": False, "message": "Không tìm thấy SKU"}, status=404)
            return

        if path == "/api/reset":
            # Reset pipeline records
            save_json(PIPELINE_FILE, [])
            self._send_json({"success": True, "message": "Đã làm mới dữ liệu Pipeline"})
            return

        self.send_error(404, "Endpoint not found")

    def _send_json(self, data, status=200):
        resp_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(resp_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(resp_bytes)

def run():
    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingHTTPServer(server_address, MinhAnApiHandler)
    print(f"============================================================")
    print(f"  AI AGENT XỬ LÝ CƠ HỘI BÁN HÀNG B2B - CÔNG TY MINH AN")
    print(f"  Đang chạy tại: http://localhost:{PORT}")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang tắt server...")
        httpd.server_close()

if __name__ == "__main__":
    run()

