"""cart 模块单元测试。

两种运行方式（任选其一，都不需要额外装东西）：
    python -m unittest discover -s tests -t . -v
    python -m pytest tests -v        # 若已安装 pytest

覆盖点：
    * 添加商品、同名同价自动累加、同名不同价分行
    * 单价/数量/名称的非法输入校验
    * 小计、行小计的四舍五入与浮点误差
    * 修改数量、部分删除、整行删除、清空
    * 学生折扣金额、自定义折扣率、非学生不打折
    * checkout 结算内容、空购物车、结算后是否清空
"""

from __future__ import annotations

from decimal import Decimal
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cart import (  # noqa: E402
    CartError,
    CartItem,
    EmptyCartError,
    InvalidPriceError,
    InvalidQuantityError,
    ItemNotFoundError,
    ShoppingCart,
    Receipt,
    format_money,
    round_money,
    to_decimal,
)


class TestMoneyHelpers(unittest.TestCase):
    def test_to_decimal_avoids_float_error(self):
        # 0.1 + 0.2 的经典浮点误差：走 Decimal 后必须是精确的 0.3
        self.assertEqual(to_decimal(0.1) + to_decimal(0.2), Decimal("0.3"))

    def test_to_decimal_accepts_str_int_float(self):
        self.assertEqual(to_decimal("5.50"), Decimal("5.50"))
        self.assertEqual(to_decimal(7), Decimal("7"))
        self.assertEqual(to_decimal(2.35), Decimal("2.35"))

    def test_to_decimal_rejects_bool_nan_inf_text(self):
        for bad in [True, False]:
            with self.assertRaises(InvalidPriceError):
                to_decimal(bad)
        for bad in ["nan", "inf", "-inf", "abc", "", None, []]:
            with self.assertRaises(CartError):
                to_decimal(bad)

    def test_round_money_half_up(self):
        self.assertEqual(round_money(Decimal("2.345")), Decimal("2.35"))
        self.assertEqual(round_money(Decimal("2.344")), Decimal("2.34"))
        self.assertEqual(format_money(Decimal("2.5"), "¥"), "¥2.50")


class TestAddItem(unittest.TestCase):
    def setUp(self):
        self.cart = ShoppingCart()

    def test_add_single_item(self):
        item = self.cart.add_item("苹果", "12.50", 2)
        self.assertEqual(item.name, "苹果")
        self.assertEqual(item.unit_price, Decimal("12.50"))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.line_total, Decimal("25.00"))
        self.assertEqual(self.cart.item_count, 2)
        self.assertEqual(self.cart.distinct_count, 1)

    def test_default_quantity_is_one(self):
        item = self.cart.add_item("牛奶", 3.8)
        self.assertEqual(item.quantity, 1)

    def test_same_name_same_price_merges(self):
        self.cart.add_item("苹果", "12.50", 2)
        self.cart.add_item("苹果", "12.50", 3)
        self.assertEqual(self.cart.distinct_count, 1)
        self.assertEqual(self.cart.item_count, 5)
        self.assertEqual(self.cart.items[0].quantity, 5)

    def test_same_name_different_price_creates_new_line(self):
        self.cart.add_item("苹果", "12.50", 2)
        self.cart.add_item("苹果", "9.90", 1)  # 促销价
        self.assertEqual(self.cart.distinct_count, 2)
        self.assertEqual(self.cart.subtotal, Decimal("34.90"))

    def test_name_is_stripped(self):
        item = self.cart.add_item("  香蕉  ", "4.00")
        self.assertEqual(item.name, "香蕉")

    def test_empty_name_raises(self):
        for bad in ["", "   ", None]:
            with self.assertRaises(CartError):
                self.cart.add_item(bad, "5.00")

    def test_invalid_price_raises(self):
        for bad in ["0", -1, "abc", None, True]:
            with self.assertRaises(CartError):
                self.cart.add_item("测试", bad)

    def test_invalid_quantity_raises(self):
        for bad in [0, -2, 1.5, "abc", None]:
            with self.assertRaises(CartError):
                self.cart.add_item("测试", "5.00", bad)

    def test_quantity_str_and_float_integer_are_accepted(self):
        self.cart.add_item("A", "1.00", "3")
        self.cart.add_item("B", "1.00", 2.0)
        self.assertEqual(self.cart.item_count, 5)

    def test_cart_item_self_validates(self):
        with self.assertRaises(InvalidPriceError):
            CartItem("A", Decimal("0"), 1)
        with self.assertRaises(InvalidQuantityError):
            CartItem("A", Decimal("1"), 0)
        with self.assertRaises(CartError):
            CartItem(" ", Decimal("1"), 1)


class TestTotals(unittest.TestCase):
    def test_subtotal_sums_lines(self):
        cart = ShoppingCart()
        cart.add_item("苹果", "12.50", 2)     # 25.00
        cart.add_item("牛奶", "3.80", 3)      # 11.40
        cart.add_item("笔记本", "9.90", 5)    # 49.50
        self.assertEqual(cart.subtotal, Decimal("85.90"))
        self.assertEqual(cart.item_count, 10)

    def test_line_rounding_is_half_up(self):
        cart = ShoppingCart()
        cart.add_item("称重商品", "3.333", 1)
        self.assertEqual(cart.items[0].line_total, Decimal("3.33"))
        cart2 = ShoppingCart()
        cart2.add_item("称重商品", "3.335", 1)
        self.assertEqual(cart2.items[0].line_total, Decimal("3.34"))

    def test_subtotal_equals_sum_of_rounded_lines(self):
        cart = ShoppingCart()
        cart.add_item("A", "1.005", 3)  # 3.02
        cart.add_item("B", "2.004", 2)  # 4.01
        expected = sum(it.line_total for it in cart.items)
        self.assertEqual(cart.subtotal, expected)

    def test_empty_cart_totals_are_zero(self):
        cart = ShoppingCart()
        self.assertEqual(cart.subtotal, Decimal("0.00"))
        self.assertEqual(cart.total(True), Decimal("0.00"))
        self.assertEqual(cart.total(False), Decimal("0.00"))
        self.assertEqual(cart.discount_amount(True), Decimal("0.00"))

    def test_float_price_does_not_drift(self):
        cart = ShoppingCart()
        cart.add_item("A", 0.1, 3)  # 0.30 而不是 0.30000000000000004
        cart.add_item("B", 0.2, 1)
        self.assertEqual(cart.subtotal, Decimal("0.50"))


class TestStudentDiscount(unittest.TestCase):
    def setUp(self):
        self.cart = ShoppingCart()
        self.cart.add_item("苹果", "12.50", 2)   # 25.00
        self.cart.add_item("牛奶", "3.80", 3)    # 11.40

    def test_default_rate_is_ninety_percent(self):
        self.assertEqual(self.cart.student_rate, Decimal("0.90"))

    def test_discount_amount_and_total(self):
        # 小计 36.40，9 折 → 折扣 3.64，应付 32.76
        self.assertEqual(self.cart.subtotal, Decimal("36.40"))
        self.assertEqual(self.cart.discount_amount(True), Decimal("3.64"))
        self.assertEqual(self.cart.total(True), Decimal("32.76"))

    def test_no_discount_for_non_student(self):
        self.assertEqual(self.cart.discount_amount(False), Decimal("0.00"))
        self.assertEqual(self.cart.total(False), Decimal("36.40"))

    def test_custom_rate(self):
        cart = ShoppingCart(student_rate="0.85")
        cart.add_item("A", "100.00", 1)
        self.assertEqual(cart.discount_amount(True), Decimal("15.00"))
        self.assertEqual(cart.total(True), Decimal("85.00"))

    def test_rate_one_means_no_discount(self):
        cart = ShoppingCart(student_rate=1)
        cart.add_item("A", "100.00", 1)
        self.assertEqual(cart.discount_amount(True), Decimal("0.00"))
        self.assertEqual(cart.total(True), Decimal("100.00"))

    def test_invalid_rate_raises(self):
        for bad in [0, -0.1, 1.5, "abc"]:
            with self.assertRaises(CartError):
                ShoppingCart(student_rate=bad)

    def test_discount_rounds_to_cent(self):
        cart = ShoppingCart()
        cart.add_item("A", "0.99", 1)  # 小计 0.99，折扣 0.099 → 0.10
        self.assertEqual(cart.discount_amount(True), Decimal("0.10"))
        self.assertEqual(cart.total(True), Decimal("0.89"))


class TestModify(unittest.TestCase):
    def setUp(self):
        self.cart = ShoppingCart()
        self.cart.add_item("苹果", "12.50", 2)
        self.cart.add_item("牛奶", "3.80", 3)

    def test_set_quantity(self):
        self.cart.set_quantity("苹果", 5)
        self.assertEqual(self.cart.items[0].quantity, 5)
        self.assertEqual(self.cart.subtotal, Decimal("73.90"))

    def test_set_quantity_zero_removes(self):
        self.cart.set_quantity("苹果", 0)
        self.assertEqual(self.cart.distinct_count, 1)

    def test_remove_whole_line(self):
        self.cart.remove_item("苹果")
        self.assertEqual(self.cart.distinct_count, 1)
        self.assertEqual(self.cart.items[0].name, "牛奶")

    def test_remove_partial_quantity(self):
        self.cart.remove_item("牛奶", 1)
        self.assertEqual(self.cart.items[1].quantity, 2)

    def test_remove_more_than_existing_drops_line(self):
        self.cart.remove_item("牛奶", 10)
        self.assertEqual(self.cart.distinct_count, 1)

    def test_remove_missing_item_raises(self):
        with self.assertRaises(ItemNotFoundError):
            self.cart.remove_item("西瓜")

    def test_clear(self):
        self.cart.clear()
        self.assertEqual(len(self.cart), 0)
        self.assertFalse(bool(self.cart))


class TestCheckout(unittest.TestCase):
    def setUp(self):
        self.cart = ShoppingCart()
        self.cart.add_item("苹果", "12.50", 2)   # 25.00
        self.cart.add_item("牛奶", "3.80", 3)    # 11.40

    def test_checkout_returns_receipt(self):
        receipt = self.cart.checkout(student=True)
        self.assertIsInstance(receipt, Receipt)
        self.assertEqual(receipt.subtotal, Decimal("36.40"))
        self.assertEqual(receipt.discount_amount, Decimal("3.64"))
        self.assertEqual(receipt.total, Decimal("32.76"))
        self.assertEqual(receipt.item_count, 5)
        self.assertTrue(receipt.student)
        self.assertEqual(len(receipt.lines), 2)

    def test_checkout_without_student_has_no_discount(self):
        receipt = self.cart.checkout(student=False)
        self.assertEqual(receipt.discount_amount, Decimal("0.00"))
        self.assertEqual(receipt.total, Decimal("36.40"))
        self.assertEqual(receipt.discount_rate, Decimal("1"))

    def test_checkout_clears_cart_by_default(self):
        self.cart.checkout(student=True)
        self.assertEqual(len(self.cart), 0)

    def test_checkout_keeps_cart_when_clear_false(self):
        self.cart.checkout(student=True, clear=False)
        self.assertEqual(len(self.cart), 5)

    def test_checkout_empty_cart_raises(self):
        empty = ShoppingCart()
        with self.assertRaises(EmptyCartError):
            empty.checkout()

    def test_receipt_text_contains_key_numbers(self):
        receipt = self.cart.checkout(student=True)
        text = receipt.as_text()
        self.assertIn("苹果", text)
        self.assertIn("36.40", text)
        self.assertIn("3.64", text)
        self.assertIn("32.76", text)
        self.assertIn("学生折扣", text)
        self.assertIn("应付总额", text)

    def test_receipt_as_dict(self):
        receipt = self.cart.checkout(student=True)
        data = receipt.as_dict()
        self.assertEqual(data["subtotal"], "36.40")
        self.assertEqual(data["total"], "32.76")
        self.assertEqual(len(data["lines"]), 2)
        self.assertEqual(data["lines"][0]["name"], "苹果")

    def test_receipt_lines_are_snapshot(self):
        # 结算后继续操作购物车，不应影响已生成的小票
        receipt = self.cart.checkout(student=True, clear=False)
        self.cart.add_item("香蕉", "4.00", 1)
        self.assertEqual(len(receipt.lines), 2)
        self.assertEqual(receipt.total, Decimal("32.76"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
