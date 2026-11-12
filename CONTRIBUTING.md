# 协作开发规范

本项目按「主分支保护 + 功能分支 + Pull Request」的方式协作，多人同时改代码也不会互相覆盖。

## 1. 分支模型

| 分支 | 用途 | 谁能直接 push |
| --- | --- | --- |
| `main` | 始终可运行、测试全绿 | 不允许直接 push，只能通过 PR 合入 |
| `feature/<功能名>` | 新功能，如 `feature/student-discount` | 功能负责人 |
| `fix/<问题名>` | 修 bug，如 `fix/rounding-half-up` | 修复人 |
| `docs/<主题>` | 只改文档 | 文档负责人 |
| `refactor/<模块>` | 不改行为的重构 | 重构人 |

命名统一小写 + 连字符，例如 `feature/coupon-support`、`fix/empty-cart-checkout`。

```bash
git switch main
git pull origin main                 # 先同步最新代码
git switch -c feature/coupon-support # 再开新分支
```

## 2. 提交信息格式

```
<type>(<scope>): <概述>

<可选：为什么要这么改>
```

- `type`：`feat` / `fix` / `test` / `docs` / `refactor` / `chore`
- `scope`：`cart` / `cli` / `tests` / `docs`
- 概述用中文或英文都行，一句话说清改了什么，不超过 50 字

示例：

```
feat(cart): 支持同名不同价商品分行
fix(cart): 折扣金额四舍五入到分，避免 0.01 误差
test(tests): 补充结算后清空购物车的用例
```

## 3. 提交前必做

```bash
python -m unittest discover -s tests -t . -v   # 必须全绿
python main.py --demo                          # 手跑一遍，确认菜单/结算没坏
```

## 4. Pull Request 流程

1. 推送分支：`git push -u origin feature/coupon-support`
2. 在 GitHub 页面点 **Compare & pull request**，按 `.github/pull_request_template.md` 填写
3. 至少 1 位同学 review，重点看：金额是否仍走 `Decimal`、边界用例是否补了测试
4. CI / 本地测试全绿后，用 **Squash and merge** 合入 `main`
5. 合并后删除远端功能分支，本地 `git switch main && git pull`

## 5. 代码约定

- 金额只允许 `Decimal`，不要新增 `float` 参与运算；入口统一走 `to_decimal()`
- 所有对外方法先校验参数，非法输入抛 `CartError` 及其子类，不要抛裸 `Exception`
- 新增功能必须同时补 `tests/test_cart.py` 的用例
- 公共方法写中文 docstring，说明参数、返回值与异常
- 不引入第三方运行依赖（保持 `cart.py` 零依赖，方便别人直接拷走）

## 6. 冲突处理

```bash
git switch feature/coupon-support
git fetch origin
git rebase origin/main      # 或 git merge origin/main
# 解决冲突 → 跑测试 → git add . → git rebase --continue
git push --force-with-lease # rebase 后需要用这个，不要用 --force
```

## 7. 分工建议（3 人小组）

| 角色 | 负责 |
| --- | --- |
| A | `cart.py` 核心逻辑（金额、折扣、结算） |
| B | `main.py` 命令行与交互、`--demo` |
| C | `tests/` 用例、README 与 CI 配置 |

每人对自己的分支负责，改动跨模块时提前在群里说一句，避免同时改同一个文件。
