"""购物车核心模块。

功能：
    * 添加商品，记录商品数量与单价（金额统一使用 Decimal，避免浮点误差）
    * 同名同价商品自动累加数量；同名不同价视为两行（例如促销价 / 原价）
    * 修改数量、删除商品、清空购物车
    * 计算小计、学生折扣金额与应付总价
    * checkout 结算，生成小票（Receipt）

不依赖任何第三方库，Python 3.9+ 即可运行。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import unicodedata

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #
class CartError(ValueError):
    """购物车相关错误的基类（继承 ValueError，方便 CLI 统一捕获）。"""


class InvalidPriceError(CartError):
    """单价非法：非数值、NaN/Inf、小于等于 0。"""


class InvalidQuantityError(CartError):
    """数量非法：不是正整数。"""


class ItemNotFoundError(CartError):
    """购物车中找不到指定商品。"""


class EmptyCartError(CartError):
    """购物车为空，无法结算。"""


# --------------------------------------------------------------------------- #
# 金额工具
# --------------------------------------------------------------------------- #
def to_decimal(value, field_name: str = "数值") -> Decimal:
    """把 int / float / str / Decimal 统一转换成 Decimal。

    统一走 str() 中转（Decimal(str(0.1)) == 0.1），避免二进制浮点误差。
    布尔值、NaN、Inf、无法解析的字符串一律拒绝。
    """
    if isinstance(value, bool):  # bool 是 int 的子类，必须单独拦
        raise InvalidPriceError(f"{field_name}不能是布尔值")
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, (int, float, str)):
        try:
            d = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, ArithmeticError) as exc:
            raise InvalidPriceError(f"{field_name}格式不正确: {value!r}") from exc
    else:
        raise InvalidPriceError(f"{field_name}类型不支持: {type(value).__name__}")
    if not d.is_finite():
        raise InvalidPriceError(f"{field_name}必须是有限数值: {value!r}")
    return d


def round_money(value: Decimal) -> Decimal:
    """按四舍五入（ROUND_HALF_UP）保留两位小数。"""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def format_money(value: Decimal, currency: str = "") -> str:
    """金额格式化，固定两位小数。"""
    return f"{currency}{value:.2f}"


# --------------------------------------------------------------------------- #
# 商品行
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CartItem:
    """购物车中的一行：商品名 + 单价 + 数量。"""

    name: str
    unit_price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise CartError("商品名称不能为空")
        if self.unit_price <= 0:
            raise InvalidPriceError("单价必须大于 0")
        if self.quantity <= 0:
            raise InvalidQuantityError("数量必须是正整数")

    @property
    def line_total(self) -> Decimal:
        """本行小计 = 单价 × 数量（四舍五入到分）。"""
        return round_money(self.unit_price * self.quantity)


# --------------------------------------------------------------------------- #
# 结算小票
# --------------------------------------------------------------------------- #
def _display_width(text: str) -> int:
    """计算字符串显示宽度，中日韩全角字符按 2 列算。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int, align: str = "left") -> str:
    gap = max(0, width - _display_width(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


@dataclass(frozen=True)
class Receipt:
    """一次结算的结果（不可变）。"""

    lines: tuple[CartItem, ...]
    subtotal: Decimal
    discount_rate: Decimal
    discount_amount: Decimal
    total: Decimal
    item_count: int
    student: bool

    def as_dict(self) -> dict:
        return {
            "lines": [
                {
                    "name": it.name,
                    "unit_price": str(it.unit_price),
                    "quantity": it.quantity,
                    "line_total": str(it.line_total),
                }
                for it in self.lines
            ],
            "subtotal": str(self.subtotal),
            "discount_rate": str(self.discount_rate),
            "discount_amount": str(self.discount_amount),
            "total": str(self.total),
            "item_count": self.item_count,
            "student": self.student,
        }

    def as_text(self, currency: str = "¥") -> str:
        name_w, price_w, qty_w, line_w = 18, 10, 6, 12
        total_w = name_w + price_w + qty_w + line_w
        sep = "-" * total_w

        rows = [
            _pad("购物车结算小票", total_w, "center"),
            sep,
            _pad("商品", name_w)
            + _pad("单价", price_w, "right")
            + _pad("数量", qty_w, "right")
            + _pad("小计", line_w, "right"),
            sep,
        ]
        for it in self.lines:
            rows.append(
                _pad(it.name, name_w)
                + _pad(f"{it.unit_price:.2f}", price_w, "right")
                + _pad(str(it.quantity), qty_w, "right")
                + _pad(f"{it.line_total:.2f}", line_w, "right")
            )
        rows.append(sep)
        rows.append(_pad("小计", total_w - 12) + _pad(format_money(self.subtotal, currency), 12, "right"))
        if self.student and self.discount_amount > 0:
            percent = (Decimal(1) - self.discount_rate) * 100
            label = f"学生折扣 (-{percent.normalize():f}%)"
            rows.append(_pad(label, total_w - 12) + _pad("-" + format_money(self.discount_amount, currency), 12, "right"))
        rows.append(_pad("应付总额", total_w - 12) + _pad(format_money(self.total, currency), 12, "right"))
        rows.append(sep)
        rows.append(
            _pad(
                f"共 {self.item_count} 件商品 / {len(self.lines)} 种商品"
                + ("，已享受学生折扣" if self.student and self.discount_amount > 0 else ""),
                total_w,
                "center",
            )
        )
        return "\n".join(rows)


# --------------------------------------------------------------------------- #
# 购物车
# --------------------------------------------------------------------------- #
class ShoppingCart:
    """购物车。

    `student_rate` 为学生折扣率，默认 0.90（即 9 折，减 10%）。
    """

    DEFAULT_STUDENT_RATE = Decimal("0.90")

    def __init__(self, student_rate: Decimal | float | str | None = None) -> None:
        self._items: list[CartItem] = []
        self.student_rate = (
            self.DEFAULT_STUDENT_RATE if student_rate is None else self._check_rate(student_rate)
        )

    # ---------------------------- 基础属性 ---------------------------- #
    @staticmethod
    def _check_rate(rate) -> Decimal:
        d = to_decimal(rate, "折扣率")
        if d <= 0 or d > 1:
            raise CartError(f"折扣率必须在 (0, 1] 之间，收到 {rate!r}")
        return d

    @property
    def student_rate(self) -> Decimal:
        return self._student_rate

    @student_rate.setter
    def student_rate(self, rate) -> None:
        self._student_rate = self._check_rate(rate)

    @property
    def items(self) -> list[CartItem]:
        """当前所有商品行（副本，外部修改不影响购物车）。"""
        return list(self._items)

    @property
    def distinct_count(self) -> int:
        """商品种类数。"""
        return len(self._items)

    @property
    def item_count(self) -> int:
        """商品总件数（数量之和）。"""
        return sum(it.quantity for it in self._items)

    def __len__(self) -> int:
        return self.item_count

    def __iter__(self):
        return iter(self._items)

    def __bool__(self) -> bool:
        return bool(self._items)

    # ---------------------------- 校验 ---------------------------- #
    @staticmethod
    def _clean_name(name) -> str:
        if not isinstance(name, str):
            raise CartError(f"商品名称必须是字符串，收到 {type(name).__name__}")
        name = name.strip()
        if not name:
            raise CartError("商品名称不能为空")
        return name

    @staticmethod
    def _clean_price(price) -> Decimal:
        d = to_decimal(price, "单价")
        if d <= 0:
            raise InvalidPriceError(f"单价必须大于 0，收到 {price!r}")
        if d.as_tuple().exponent < -2:
            # 只提示不报错：内部仍按精确值计算，展示时四舍五入到分
            pass
        return d

    @staticmethod
    def _clean_quantity(quantity) -> int:
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            if isinstance(quantity, str) and quantity.strip().isdigit():
                quantity = int(quantity.strip())
            elif isinstance(quantity, float) and quantity.is_integer():
                quantity = int(quantity)
            else:
                raise InvalidQuantityError(f"数量必须是正整数，收到 {quantity!r}")
        if quantity <= 0:
            raise InvalidQuantityError(f"数量必须大于 0，收到 {quantity!r}")
        return quantity

    def _find_index(self, name: str, unit_price: Decimal | None = None) -> int | None:
        for idx, it in enumerate(self._items):
            if it.name == name and (unit_price is None or it.unit_price == unit_price):
                return idx
        return None

    def _require_index(self, name: str, unit_price: Decimal | None = None) -> int:
        idx = self._find_index(name, unit_price)
        if idx is None:
            raise ItemNotFoundError(f"购物车中没有商品: {name}")
        return idx

    # ---------------------------- 增删改 ---------------------------- #
    def add_item(self, name, unit_price, quantity: int = 1) -> CartItem:
        """添加商品。

        同名且单价相同的商品会累加数量，否则新增一行。
        返回添加后（合并后）的商品行。
        """
        name = self._clean_name(name)
        price = self._clean_price(unit_price)
        qty = self._clean_quantity(quantity)

        idx = self._find_index(name, price)
        if idx is None:
            item = CartItem(name=name, unit_price=price, quantity=qty)
            self._items.append(item)
        else:
            item = replace(self._items[idx], quantity=self._items[idx].quantity + qty)
            self._items[idx] = item
        return item

    def set_quantity(self, name, quantity, unit_price=None) -> None:
        """把某商品的数量改为指定值；数量为 0 时等价于删除。"""
        name = self._clean_name(name)
        qty = self._clean_quantity(quantity) if not _is_zero(quantity) else 0
        price = None if unit_price is None else self._clean_price(unit_price)
        idx = self._require_index(name, price)
        if qty == 0:
            del self._items[idx]
        else:
            self._items[idx] = replace(self._items[idx], quantity=qty)

    def remove_item(self, name, quantity: int | None = None, unit_price=None) -> None:
        """删除商品；不传 quantity 时整行删除，传了则只减对应数量。"""
        name = self._clean_name(name)
        price = None if unit_price is None else self._clean_price(unit_price)
        idx = self._require_index(name, price)
        if quantity is None:
            del self._items[idx]
            return
        qty = self._clean_quantity(quantity)
        remaining = self._items[idx].quantity - qty
        if remaining <= 0:
            del self._items[idx]
        else:
            self._items[idx] = replace(self._items[idx], quantity=remaining)

    def clear(self) -> None:
        """清空购物车。"""
        self._items.clear()

    # ---------------------------- 金额 ---------------------------- #
    @property
    def subtotal(self) -> Decimal:
        """商品小计 = 各行小计之和（小数位已统一到分）。"""
        return round_money(sum((it.line_total for it in self._items), ZERO))

    def discount_amount(self, student: bool = True) -> Decimal:
        """学生折扣金额；非学生或折扣率为 1 时为 0。"""
        if not student or self.student_rate >= 1:
            return ZERO
        return round_money(self.subtotal * (Decimal(1) - self.student_rate))

    def total(self, student: bool = True) -> Decimal:
        """应付总价 = 小计 - 学生折扣。"""
        if not self._items:
            return ZERO
        return round_money(self.subtotal - self.discount_amount(student))

    # ---------------------------- 结算 ---------------------------- #
    def checkout(self, student: bool = False, clear: bool = True) -> Receipt:
        """checkout 结算：生成小票。

        student=True 时按学生折扣计算；clear=True（默认）结算后清空购物车。
        """
        if not self._items:
            raise EmptyCartError("购物车是空的，无法结算")

        subtotal = self.subtotal
        discount = self.discount_amount(student)
        total = round_money(subtotal - discount)
        receipt = Receipt(
            lines=tuple(self._items),
            subtotal=subtotal,
            discount_rate=self.student_rate if student else Decimal(1),
            discount_amount=discount,
            total=total,
            item_count=self.item_count,
            student=student,
        )
        if clear:
            self.clear()
        return receipt


def _is_zero(value) -> bool:
    """判断是否为 0（用于 set_quantity 允许传 0 表示删除）。"""
    try:
        return to_decimal(value, "数量") == 0
    except CartError:
        return False
