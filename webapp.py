"""购物车 Web 版：标准库 http.server 提供 JSON API 与网页。

只用 Python 标准库，不装 Flask 也能跑；业务逻辑全部复用 cart.py，
所以金额规则、学生折扣、结算小票与命令行版完全一致。

接口：
    GET    /api/state          当前购物车状态
    POST   /api/items          添加商品  {"name":..., "price":..., "quantity":...}
    PUT    /api/items          修改数量  {"name":..., "price":..., "quantity":...}
    DELETE /api/items          删除整行  {"name":..., "price":...}
    POST   /api/student        切换学生身份 {"student": true/false}
    POST   /api/clear          清空购物车
    POST   /api/checkout       结算      {"student": true/false, "clear": true/false}
"""

from __future__ import annotations

import argparse
import json
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cart import CartError, ShoppingCart

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
INDEX_FILE = WEB_DIR / "index.html"


def money(value: Decimal) -> str:
    """金额统一输出两位小数的字符串，前端不再自己算。"""
    return f"{value:.2f}"


class CartService:
    """把 ShoppingCart 包成线程安全的服务对象，供 HTTP handler 调用。"""

    def __init__(self, student_rate=None) -> None:
        self._cart = ShoppingCart(student_rate=student_rate)
        self._student = False
        self._lock = threading.Lock()

    @property
    def cart(self) -> ShoppingCart:
        return self._cart

    def state(self) -> dict:
        cart = self._cart
        return {
            "items": [
                {
                    "name": item.name,
                    "unit_price": money(item.unit_price),
                    "quantity": item.quantity,
                    "line_total": money(item.line_total),
                }
                for item in cart.items
            ],
            "subtotal": money(cart.subtotal),
            "discount_rate": money(cart.student_rate),
            "discount": money(cart.discount_amount(self._student)),
            "total": money(cart.total(self._student)),
            "item_count": cart.item_count,
            "distinct_count": cart.distinct_count,
            "student": self._student,
        }

    def add_item(self, name, price, quantity) -> dict:
        with self._lock:
            self._cart.add_item(name, price, quantity)
            return self.state()

    def set_quantity(self, name, price, quantity) -> dict:
        with self._lock:
            self._cart.set_quantity(name, quantity, price)
            return self.state()

    def remove_item(self, name, price) -> dict:
        with self._lock:
            self._cart.remove_item(name, unit_price=price)
            return self.state()

    def set_student(self, student: bool) -> dict:
        with self._lock:
            self._student = bool(student)
            return self.state()

    def clear(self) -> dict:
        with self._lock:
            self._cart.clear()
            return self.state()

    def checkout(self, student: bool | None = None, clear: bool = True) -> dict:
        with self._lock:
            if student is None:
                student = self._student
            receipt = self._cart.checkout(student=bool(student), clear=clear)
            payload = receipt.as_dict()
            payload["text"] = receipt.as_text()
            payload["state"] = self.state()
            return payload


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = handler.headers.get("Content-Length") or "0"
    try:
        raw = handler.rfile.read(int(length)) if int(length) > 0 else b"{}"
    except ValueError as exc:
        raise CartError("Content-Length 不合法") from exc
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CartError("请求体不是合法的 JSON") from exc
    if not isinstance(data, dict):
        raise CartError("请求体必须是 JSON 对象")
    return data


def make_handler(service: CartService) -> type:
    """生成绑定了指定 service 的 handler 类（每个服务一个实例，方便测试）。"""

    class CartHandler(BaseHTTPRequestHandler):
        server_version = "ShoppingCartWeb/1.0"

        # ---------- 基础工具 ---------- #
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _error(self, status: int, message: str) -> None:
            self._json(status, {"error": message})

        def log_message(self, fmt, *args):  # 默认日志太吵，静默处理
            return

        # ---------- 路由 ---------- #
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                if not INDEX_FILE.exists():
                    self._error(500, "找不到 web/index.html")
                    return
                html = INDEX_FILE.read_bytes()
                self._send(200, html, "text/html; charset=utf-8")
                return
            if path == "/api/state":
                self._json(200, service.state())
                return
            self._error(404, f"没有这个路径: {path}")

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            try:
                data = _read_json(self)
                if path == "/api/items":
                    state = service.add_item(
                        data.get("name"),
                        data.get("price"),
                        data.get("quantity", 1),
                    )
                    self._json(201, state)
                    return
                if path == "/api/student":
                    self._json(200, service.set_student(bool(data.get("student"))))
                    return
                if path == "/api/clear":
                    self._json(200, service.clear())
                    return
                if path == "/api/checkout":
                    payload = service.checkout(
                        student=data.get("student"),
                        clear=bool(data.get("clear", True)),
                    )
                    self._json(200, payload)
                    return
                self._error(404, f"没有这个路径: {path}")
            except CartError as exc:
                self._error(400, str(exc))

        def do_PUT(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/api/items":
                self._error(404, f"没有这个路径: {path}")
                return
            try:
                data = _read_json(self)
                state = service.set_quantity(
                    data.get("name"), data.get("price"), data.get("quantity")
                )
                self._json(200, state)
            except CartError as exc:
                self._error(400, str(exc))

        def do_DELETE(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/api/items":
                self._error(404, f"没有这个路径: {path}")
                return
            try:
                data = _read_json(self)
                state = service.remove_item(data.get("name"), data.get("price"))
                self._json(200, state)
            except CartError as exc:
                self._error(400, str(exc))

    return CartHandler


def create_server(host: str = "127.0.0.1", port: int = 8000, service: CartService | None = None):
    """创建（但不启动）HTTP 服务；port=0 时由系统分配端口，方便测试。"""
    service = service or CartService()
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    return httpd


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="购物车 Web 版（标准库实现，无需第三方依赖）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认本机）")
    parser.add_argument("--port", type=int, default=8000, help="端口（默认 8000）")
    parser.add_argument("--rate", default=None, help="学生折扣率，如 0.85 表示 85 折")
    args = parser.parse_args(argv)

    service = CartService(student_rate=args.rate)
    httpd = create_server(args.host, args.port, service)
    url = f"http://{args.host}:{httpd.server_address[1]}/"
    print(f"购物车 Web 版已启动：{url}")
    print("按 Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
