# 项目修改说明

## 改了什么
<!-- 一句话说明，例如：feat(cart): 新增优惠券支持 -->

-

## 为什么要改
<!-- 需求背景 / 关联 issue，例如：Closes #12 -->

-

## 自查清单
- [ ] 金额计算仍然使用 `Decimal`，没有引入 `float` 参与运算
- [ ] 新增/修改的公共方法有中文 docstring
- [ ] 已补充或更新 `tests/test_cart.py` 中的用例
- [ ] 本地 `python -m unittest discover -s tests -t . -v` 全绿
- [ ] `python main.py --demo` 手动跑过，菜单和结算正常
- [ ] 没有引入第三方运行依赖（`cart.py` 保持零依赖）
- [ ] 文档（README / CONTRIBUTING）已同步

## 测试结果
<!-- 贴关键输出，例如：Ran 41 tests in 0.002s / OK -->

```
```
