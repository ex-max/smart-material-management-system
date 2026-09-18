#!/usr/bin/env bash
# scripts/verify.sh —— 项目质量门禁
#
# 约定（见 AGENTS.md）：任何会话/任何 agent 交付前必须让本脚本为绿。
# 设计原则：模块尚未落地时**跳过并说明**，一旦落地就必须真正检查——
# 因此这个脚本会随着项目推进自动变严，而不是一直"全绿但没检查"。
#
# 用法：make verify   （或直接 ./scripts/verify.sh）
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0
skip=0
hdr() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()  { printf '  \033[32mok\033[0m    %s\n' "$1"; }
bad() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; fail=1; }
sk()  { printf '  \033[33mskip\033[0m  %s\n' "$1"; skip=$((skip+1)); }

hdr "1/7 仓库结构"
for d in backend frontend ml docs scripts; do
  [ -d "$d" ] && ok "$d/" || bad "缺少目录 $d/"
done
for f in AGENTS.md docs/progress.md Makefile; do
  [ -f "$f" ] && ok "$f" || bad "缺少文件 $f"
done

hdr "2/7 禁止入库的内容"
if [ -d .git ]; then
  tracked=$(git ls-files | grep -E '^(data/|ml/results/|\.env$)|\.venv/|node_modules/' || true)
  [ -z "$tracked" ] && ok "data/ ml/results/ .env venv node_modules 未被跟踪" \
                    || bad "以下内容不应入库：$(echo "$tracked" | head -3 | tr '\n' ' ')"
else
  sk "尚未 git init"
fi

hdr "3/7 后端：lint + 测试"
if [ -x backend/.venv/bin/python ]; then
  if [ -f backend/pyproject.toml ]; then
    (cd backend && .venv/bin/python -m ruff check . >/tmp/v_ruff.txt 2>&1) \
      && ok "ruff 通过" || { bad "ruff 未通过（见下）"; tail -5 /tmp/v_ruff.txt | sed 's/^/        /'; }
  else
    sk "backend/pyproject.toml 尚未创建"
  fi
  if [ -d backend/tests ] && [ -n "$(ls -A backend/tests 2>/dev/null | grep -v README)" ]; then
    (cd backend && .venv/bin/python -m pytest -q >/tmp/v_pytest.txt 2>&1) \
      && ok "pytest 通过（$(grep -oE '[0-9]+ passed' /tmp/v_pytest.txt | head -1)）" \
      || { bad "pytest 未通过"; tail -8 /tmp/v_pytest.txt | sed 's/^/        /'; }
  else
    sk "backend/tests 尚无测试用例"
  fi
else
  sk "backend/.venv 不存在（后端未初始化）"
fi

hdr "4/7 前端：lint / 构建"
if [ -d frontend/node_modules ] && [ -f frontend/package.json ]; then
  (cd frontend && npm run -s lint >/tmp/v_lint.txt 2>&1) \
    && ok "前端 lint 通过" || { bad "前端 lint 未通过"; tail -5 /tmp/v_lint.txt | sed 's/^/        /'; }
else
  sk "frontend/node_modules 不存在（前端未初始化）"
fi

hdr "5/7 数据库迁移可解析"
if [ -f backend/alembic.ini ] && [ -x backend/.venv/bin/alembic ]; then
  (cd backend && .venv/bin/alembic upgrade head --sql >/tmp/v_alembic.sql 2>&1) \
    && ok "alembic 迁移链可生成 SQL（$(wc -l < /tmp/v_alembic.sql) 行）" \
    || { bad "alembic 迁移异常"; tail -5 /tmp/v_alembic.sql | sed 's/^/        /'; }
else
  sk "尚未引入 Alembic"
fi

hdr "6/7 领域不变量自检（脚本化部分）"
if [ -f scripts/check_invariants.py ]; then
  inv_py=python3
  [ -x backend/.venv/bin/python ] && inv_py=backend/.venv/bin/python
  "$inv_py" scripts/check_invariants.py && ok "不变量检查通过" || bad "不变量检查未通过"
else
  sk "scripts/check_invariants.py 尚未创建（库存对账/状态机检查将放这里）"
fi

hdr "7/7 ML：lint + 测试"
if [ -x ml/.venv/bin/python ] && [ -f ml/pyproject.toml ]; then
  if [ -d ml/erp_ml ] && [ -d ml/tests ] && [ -n "$(ls -A ml/tests 2>/dev/null | grep -v README)" ]; then
    (cd ml && .venv/bin/python -m ruff check . >/tmp/v_ml_ruff.txt 2>&1) \
      && ok "ml ruff 通过" || { bad "ml ruff 未通过（见下）"; tail -5 /tmp/v_ml_ruff.txt | sed 's/^/        /'; }
    (cd ml && .venv/bin/python -m pytest -q >/tmp/v_ml_pytest.txt 2>&1) \
      && ok "ml pytest 通过（$(grep -oE '[0-9]+ passed' /tmp/v_ml_pytest.txt | head -1)）" \
      || { bad "ml pytest 未通过"; tail -8 /tmp/v_ml_pytest.txt | sed 's/^/        /'; }
  else
    sk "ml/erp_ml 或 ml/tests 尚未落地"
  fi
else
  sk "ml/.venv 不存在（ML 未初始化，可跑 make ml-venv）"
fi

printf '\n\033[1m== 结果：%s（跳过 %d 项）==\033[0m\n' \
  "$([ $fail -eq 0 ] && echo 'PASS ✅' || echo 'FAIL ❌')" "$skip"
exit $fail
