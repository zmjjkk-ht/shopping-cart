"""webapp 模块（HTTP API）测试。

启动一个真实的本地服务（端口由系统分配），用标准库 urllib 发请求验证接口行为。

运行方式：
    python -m unittest discover -s tests -t . -v
"""

from __future__ import annotations

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp import CartService, create_server  # noqa: E402


class WebAppApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = CartService()
        cls.server = create_server("127.0.0.1", 0, cls.service)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.request("POST", "/api/clear", {})
        self.request("POST", "/api/student", {"student": False})

    def request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    # ---------------------------- 页面 ---------------------------- #
    def test_index_page_served(self):
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
        self.assertIn("购物车", body)
        self.assertIn("结算 checkout", body)
        self.assertIn("/api/state", body)

    def test_unknown_path_returns_404(self):
        status, payload = self.request("GET", "/api/nope")
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    # ---------------------------- 状态与添加 ---------------------------- #
    def test_initial_state_is_empty(self):
        status, payload = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["subtotal"], "0.00")
        self.assertEqual(payload["total"], "0.00")
        self.assertEqual(payload["item_count"], 0)

    def test_add_item(self):
        status, payload = self.request(
            "POST", "/api/items", {"name": "苹果", "price": "12.50", "quantity": 2}
        )
        self.assertEqual(status, 201)
        self.assertEqual(payload["item_count"], 2)
        self.assertEqual(payload["subtotal"], "25.00")
        self.assertEqual(payload["items"][0]["line_total"], "25.00")

    def test_add_same_name_and_price_merges(self):
        self.request("POST", "/api/items", {"name": "苹果", "price": "12.50", "quantity": 2})
        _, payload = self.request(
            "POST", "/api/items", {"name": "苹果", "price": "12.50", "quantity": 3}
        )
        self.assertEqual(payload["distinct_count"], 1)
        self.assertEqual(payload["item_count"], 5)

    def test_add_invalid_price_returns_400(self):
        status, payload = self.request(
            "POST", "/api/items", {"name": "苹果", "price": "-3", "quantity": 1}
        )
        self.assertEqual(status, 400)
        self.assertIn("单价", payload["error"])

    def test_add_empty_name_returns_400(self):
        status, payload = self.request(
            "POST", "/api/items", {"name": "   ", "price": "3.00", "quantity": 1}
        )
        self.assertEqual(status, 400)

    # ---------------------------- 修改与删除 ---------------------------- #
    def test_update_quantity(self):
        self.request("POST", "/api/items", {"name": "牛奶", "price": "3.80", "quantity": 3})
        status, payload = self.request(
            "PUT", "/api/items", {"name": "牛奶", "price": "3.80", "quantity": 1}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["item_count"], 1)
        self.assertEqual(payload["subtotal"], "3.80")

    def test_update_zero_quantity_removes_line(self):
        self.request("POST", "/api/items", {"name": "牛奶", "price": "3.80", "quantity": 2})
        _, payload = self.request(
            "PUT", "/api/items", {"name": "牛奶", "price": "3.80", "quantity": 0}
        )
        self.assertEqual(payload["items"], [])

    def test_delete_line(self):
        self.request("POST", "/api/items", {"name": "牛奶", "price": "3.80", "quantity": 2})
        status, payload = self.request(
            "DELETE", "/api/items", {"name": "牛奶", "price": "3.80"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["item_count"], 0)

    def test_delete_missing_item_returns_400(self):
        status, payload = self.request("DELETE", "/api/items", {"name": "西瓜", "price": "1.00"})
        self.assertEqual(status, 400)
        self.assertIn("没有商品", payload["error"])

    # ---------------------------- 折扣与结算 ---------------------------- #
    def test_student_toggle_affects_total(self):
        self.request("POST", "/api/items", {"name": "苹果", "price": "12.50", "quantity": 2})
        _, before = self.request("GET", "/api/state")
        self.assertEqual(before["total"], "25.00")
        self.assertEqual(before["discount"], "0.00")

        _, after = self.request("POST", "/api/student", {"student": True})
        self.assertTrue(after["student"])
        self.assertEqual(after["discount"], "2.50")
        self.assertEqual(after["total"], "22.50")

    def test_checkout_returns_receipt_and_clears(self):
        self.request("POST", "/api/items", {"name": "苹果", "price": "12.50", "quantity": 2})
        self.request("POST", "/api/items", {"name": "牛奶", "price": "3.80", "quantity": 3})
        status, payload = self.request(
            "POST", "/api/checkout", {"student": True, "clear": True}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["subtotal"], "36.40")
        self.assertEqual(payload["discount_amount"], "3.64")
        self.assertEqual(payload["total"], "32.76")
        self.assertEqual(payload["item_count"], 5)
        self.assertIn("应付总额", payload["text"])
        self.assertIn("32.76", payload["text"])
        # 结算后购物车被清空
        self.assertEqual(payload["state"]["items"], [])

    def test_checkout_keeps_cart_when_clear_false(self):
        self.request("POST", "/api/items", {"name": "苹果", "price": "12.50", "quantity": 2})
        _, payload = self.request("POST", "/api/checkout", {"student": False, "clear": False})
        self.assertEqual(payload["state"]["item_count"], 2)

    def test_checkout_empty_cart_returns_400(self):
        status, payload = self.request("POST", "/api/checkout", {"student": True})
        self.assertEqual(status, 400)
        self.assertIn("空的", payload["error"])

    # ---------------------------- 异常请求 ---------------------------- #
    def test_bad_json_returns_400(self):
        request = urllib.request.Request(
            self.base + "/api/items",
            data=b"{not json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(request, timeout=5)
            self.fail("应当抛出 HTTPError")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
            payload = json.loads(exc.read().decode("utf-8"))
            self.assertIn("JSON", payload["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
