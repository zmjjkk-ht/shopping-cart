"""购物车系统命令行入口。

用法：
    python main.py                 # 交互式菜单
    python main.py --demo          # 运行内置演示（快速查看功能与结算输出）
    python main.py --rate 0.85     # 指定学生折扣率（85 折）

菜单操作：
    1. 添加商品   2. 查看购物车   3. 修改数量   4. 删除商品
    5. 结算       6. 清空购物车   7. 切换学生身份   0. 退出
"""

from __future__ import annotations

import argparse
import sys

from cart import CartError, ShoppingCart, format_money


LINE = "=" * 46


def _ask(prompt: str) -> str:
    """读取一行输入；用户按 Ctrl+C / Ctrl+Z 时抛出 EOFError 交给上层处理。"""
    return input(prompt).strip()


def _ask_price() -> str:
    while True:
        raw = _ask("单价: ")
        try:
            from decimal import Decimal

            Decimal(raw)
            return raw
        except Exception:
            print("  ! 单价必须是数字，请重新输入")


def _ask_quantity(default: int = 1) -> int:
    raw = _ask(f"数量（回车默认 {default}）: ")
    if not raw:
        return default
    while True:
        try:
            qty = int(raw)
            if qty <= 0:
                raise ValueError
            return qty
        except ValueError:
            raw = _ask("  ! 数量必须是正整数，请重新输入: ")


def show_cart(cart: ShoppingCart, student: bool) -> None:
    print(LINE)
    if not cart:
        print("购物车是空的")
        print(LINE)
        return
    print(f"{'序号':<4}{'商品':<16}{'单价':>8}{'数量':>6}{'小计':>10}")
    print("-" * 46)
    for i, it in enumerate(cart.items, start=1):
        print(f"{i:<6}{it.name:<14}{it.unit_price:>10.2f}{it.quantity:>6}{it.line_total:>12.2f}")
    print("-" * 46)
    print(f"商品小计: {format_money(cart.subtotal, '¥')}")
    if student:
        print(f"学生折扣: -{format_money(cart.discount_amount(True), '¥')}")
    print(f"应付总额: {format_money(cart.total(student), '¥')}  (共 {cart.item_count} 件)")
    print(LINE)


def add_item(cart: ShoppingCart) -> None:
    name = _ask("商品名称: ")
    if not name:
        print("  ! 商品名称不能为空")
        return
    price = _ask_price()
    qty = _ask_quantity()
    item = cart.add_item(name, price, qty)
    print(f"  √ 已添加 {item.name} × {item.quantity}，单价 {format_money(item.unit_price, '¥')}")


def change_quantity(cart: ShoppingCart) -> None:
    if not cart:
        print("购物车是空的，先添加商品吧")
        return
    show_cart(cart, False)
    name = _ask("要修改的商品名称: ")
    qty = _ask_quantity()
    cart.set_quantity(name, qty)
    print(f"  √ 已将 {name} 的数量改为 {qty}")


def remove_item(cart: ShoppingCart) -> None:
    if not cart:
        print("购物车是空的，先添加商品吧")
        return
    show_cart(cart, False)
    name = _ask("要删除的商品名称: ")
    cart.remove_item(name)
    print(f"  √ 已移除 {name}")


def checkout(cart: ShoppingCart, student: bool) -> None:
    receipt = cart.checkout(student=student, clear=True)
    print()
    print(receipt.as_text())


def run_menu(cart: ShoppingCart, student: bool) -> None:
    while True:
        print()
        print(LINE)
        print("            购物车系统 (Python)")
        print(LINE)
        print(f"  1. 添加商品        2. 查看购物车")
        print(f"  3. 修改数量        4. 删除商品")
        print(f"  5. 结算 checkout   6. 清空购物车")
        state = "是" if student else "否"
        print(f"  7. 切换学生身份（当前：{state}）")
        print(f"  0. 退出")
        choice = _ask("请选择: ")

        try:
            if choice == "1":
                add_item(cart)
            elif choice == "2":
                show_cart(cart, student)
            elif choice == "3":
                change_quantity(cart)
            elif choice == "4":
                remove_item(cart)
            elif choice == "5":
                if not cart:
                    print("购物车是空的，无法结算")
                else:
                    checkout(cart, student)
                    print("  √ 结算完成，购物车已清空")
            elif choice == "6":
                cart.clear()
                print("  √ 购物车已清空")
            elif choice == "7":
                student = not student
                print(f"  √ 学生身份：{'是' if student else '否'}")
            elif choice == "0":
                print("再见！")
                return
            else:
                print("  ! 无效选项，请输入 0-7")
        except CartError as exc:
            print(f"  ! {exc}")


def run_demo(rate) -> None:
    """内置演示：添加商品 → 查看 → 结算（含学生折扣）。"""
    cart = ShoppingCart(student_rate=rate)
    print("【演示】向购物车添加商品")
    for name, price, qty in [
        ("苹果", "12.50", 2),
        ("牛奶", "3.80", 3),
        ("笔记本", "9.90", 5),
    ]:
        item = cart.add_item(name, price, qty)
        print(f"  + {item.name} × {item.quantity} @ {format_money(item.unit_price, '¥')}")

    print("\n【演示】当前购物车")
    show_cart(cart, True)

    print("\n【演示】checkout 结算（学生身份，享受折扣）")
    receipt = cart.checkout(student=True, clear=True)
    print(receipt.as_text())
    print(f"\n结算后购物车商品数：{cart.item_count}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Python 购物车（支持学生折扣与结算）")
    parser.add_argument("--demo", action="store_true", help="运行内置演示脚本")
    parser.add_argument("--rate", default=None, help="学生折扣率，如 0.9 表示 9 折（默认 0.9）")
    args = parser.parse_args(argv)

    if args.rate is None:
        cart = ShoppingCart()
    else:
        try:
            cart = ShoppingCart(student_rate=args.rate)
        except CartError as exc:
            print(f"折扣率不合法：{exc}", file=sys.stderr)
            return 2

    if args.demo:
        run_demo(cart.student_rate)
        return 0

    print(f"提示：学生折扣率 {cart.student_rate}（{format_money(cart.student_rate * 100, '')}%）")
    try:
        run_menu(cart, student=False)
    except (EOFError, KeyboardInterrupt):
        print("\n已退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
