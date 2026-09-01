#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coze_client.py — ct-samplesize v4.0 coze 后端（权威计算引擎）

职责：
  - 将本地解析好的参数打包成请求信封，调用 coze 端 R 服务。
  - 解析 coze 返回的多部件信封（数值 + 可选 R 代码/结果 + 可选可视化产物）。
  - 端点与 Bearer token 默认取自 `coze_token_embedded`（随技能发布的公共凭据，
    XOR+base64 混淆内嵌）；可用 env(CTSS_COZE_ENDPOINT / CTSS_COZE_TOKEN) 覆盖。
  - mock 模式（CTSS_COZE_MOCK=1）仍保留，用于无网络/演示场景返回样例信封。

出站授权（ct-base §5 安全模型 / docs/02-security-model.md，2026-08-19 应用）：
  - 任何发往外部端点的请求在真正发送前经 `_check_outbound_authorization` 门控：
    命中 config/config.json 的 auto_approve_endpoints 白名单（公共端点已由作者预置，
    永不弹确认）或本会话内存已授权 → 放行；否则 stderr 输出 AUTH-BLOCK + 全库统一
    确认提示，**不发送**（授权不阻断流程：返回 None，由调用方提示用户）。
  - 发往端点的 payload 经 `sanitize()` 剥离 PII（身份证 / 手机号 / 邮箱）。
  - Windows 系统代理残留（WinError 10061）→ 绕过代理直连重试一次。
  - 异常与日志绝不回显 token / payload 明文（只打异常类型与端点）。

信封契约见 adapters/coze/coze_contract.md。
"""
import hashlib
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from compute_backend import ComputeBackend, Figure, Result

# 自举 sys.path（2026-08-19 修复）：本文件通过 `adapters.coze_client` 方式导入时
# （CLI 主路径 samplesize_power.py → compute_backend → adapters.coze_client），
# sys.path 通常不含 adapters/ 目录 → 裸 `from coze_token_embedded import` 失败 →
# 内嵌端点/token 静默丢失 → coze_available() 误判"coze 不可达"。
# 这里把本文件所在目录加入 sys.path（幂等），保证两种导入方式行为一致。
_HERE_DIR = str(Path(__file__).resolve().parent)
if _HERE_DIR not in sys.path:
    sys.path.insert(0, _HERE_DIR)

# ---------------------------------------------------------------------------
# coze 信封契约漂移检测（ct-base §20.9 单入口 · 2026-08-29 修订：仅结构/数据内容不一致触发）
# ---------------------------------------------------------------------------
# 仅当 coze 返回的数据内容与本地消费接口不一致（字段别名 / 结构形变）时，自适应兼容并
# 经 HTML 横幅（_needs_upgrade / _contract_drift 驱动）提示升级。
# ⚠️ 版本号差异**不再**触发任何提醒：版本由 coze 端随发布同步，本地不比对版本号，避免无谓打扰。


def _assess_contract(parsed: dict) -> tuple:
    """结构/数据内容漂移检测（自愈优先），单一入口（ct-base §20.9 · 2026-08-29 修订）。

    仅检测「结构漂移（主·自愈）」：识别已知字段别名并自适应归一化，保证报告仍能渲染；
    映射发生时记 drift 说明，交给 rendering.py 在 HTML 横幅提示升级。对无法自适应的
    结构缺失仅记录告警、不臆造数据。别名表按 ct-samplesize 信封微调。

    ⚠️ 版本号差异**不再**触发任何提醒：版本由 coze 端随发布同步，本地不比对版本号，
    避免无谓打扰。仅当返回的「数据内容 / 结构」与本地消费接口不一致时才提示。

    Returns: (parsed, drift_notes, needs_upgrade)
      drift_notes 非空（= 检测到数据内容/结构不一致）=> 交给 rendering.py 在 HTML 横幅提示；
      needs_upgrade 仅为机器可读标记（写回 parsed），本函数**不产生任何用户可见提示**
      （用户可见提示统一只在渲染层的 HTML 横幅，避免 stderr / notes 重复提示）。
    """
    if not isinstance(parsed, dict):
        return parsed, [], False
    notes = []
    p = parsed

    # ---- 结构漂移：已知字段别名 → 本地期望字段（仅当期望字段缺/空、且别名存在时映射）----
    # 1) 主叙述：旧信封 `content` → 当前 `narrative`
    if not p.get("narrative") and isinstance(p.get("content"), str) and p["content"].strip():
        p["narrative"] = p["content"]
        notes.append("coze 响应字段已变更：主叙述由 `content` 改为 `narrative`，已自动适配")

    # 2) figures 结构兜底（dict → list；图体别名 image/svg_data/base64/svg → content）
    figs = p.get("figures")
    if isinstance(figs, dict):
        p["figures"] = [
            {"format": "svg", "content": v, "caption": k}
            for k, v in figs.items() if isinstance(v, str)
        ]
        notes.append("coze 响应结构已变更：figures 由 dict 改为 list，已自动适配")
    elif isinstance(figs, list):
        for i, f in enumerate(figs):
            if isinstance(f, dict) and "content" not in f:
                for fa in ("svg", "image", "svg_data", "base64"):
                    if isinstance(f.get(fa), str):
                        f["content"] = f[fa]
                        notes.append(
                            f"coze 响应字段已变更：figures[{i}] 图体由 `{fa}` 改为 `content`，已自动适配")
                        break

    # 去重（保持顺序）
    seen, uniq = set(), []
    for n in notes:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return p, uniq, bool(uniq)


# ---------------------------------------------------------------------------
# coze 调用并发限流（2026-08-28 新增 · ct-base §20.10 全库统一标准）
# ---------------------------------------------------------------------------
# 相邻两次 coze /run 出站调用之间必须间隔 ≥1 秒，防止触发 coze 端频控（429）。
# meta-analysis 实测曾因密集请求被限流至次日，整批分析失败。强制间隔是零成本护栏。
# 间隔秒数可由环境变量 COZE_META_MIN_INTERVAL（浮点秒）覆写；<=0 时关闭保护（调试用）。
_RATE_LIMIT_LOCK = threading.Lock()
_LAST_CALL_TS = 0.0  # time.monotonic() of the most recently dispatched coze POST


def _acquire_rate_limit() -> None:
    """相邻两次 coze POST 之间至少间隔 1 秒（可由 COZE_META_MIN_INTERVAL 覆写）。

    用模块级锁串行化"间隔决策"并强制最小间隔；锁内只做间隔判定 + 必要 sleep 占位，
    网络请求在锁释放后发出——既保证 ≥1s 间距，又不把网络延迟锁进临界区。
    作用域：同一 Python 进程内多线程并发（本技能典型调用场景）。跨进程并发需另加
    文件锁，当前未实现（ct-base §20.10 边界）。
    """
    try:
        interval = float(os.environ.get("COZE_META_MIN_INTERVAL", "1.0"))
    except (TypeError, ValueError):
        interval = 1.0
    if interval <= 0:
        return
    global _LAST_CALL_TS
    with _RATE_LIMIT_LOCK:
        now = time.monotonic()
        wait = interval - (now - _LAST_CALL_TS)
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
        _LAST_CALL_TS = now


try:
    from coze_token_embedded import (
        get_token as _embedded_get_token,
        get_endpoint as _embedded_get_endpoint,
    )
except Exception:  # pragma: no cover - 内嵌凭据缺失时退化为仅 env/mock
    _embedded_get_token = None
    _embedded_get_endpoint = None

# ---------------------------------------------------------------------------
# 出站授权确认提示（ct-base language_policy：一次性提示强制走 i18n，禁止硬编码）
# ---------------------------------------------------------------------------
try:
    from i18n import t as _i18n_t  # 单一事实来源：scripts/i18n.py _MESSAGES
    _HAS_I18N = True
except Exception:  # pragma: no cover - 测试环境缺 scripts 路径时退化
    _HAS_I18N = False
    _i18n_t = None


# ---------------------------------------------------------------------------
# §8.6 query_origin：调用来源标识（全库统一，审计 / 归因 / 限流）
# ---------------------------------------------------------------------------
def _compute_query_origin() -> str:
    """§8.6 query_origin：按本机 hostname 计算稳定标识，由客户端（技能安装设备）生成。

    - 格式 `sha256:<64 hex>`；同一台机器每次返回完全相同的值（便于按机器审计/限流）。
    - SHA256 单向不可逆，不含明文 hostname / IP / 任何 PII。
    - **必须由客户端生成随请求发出**，禁止由 coze 服务器兜底生成（服务器容器重建即漂移）。
    """
    return "sha256:" + hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# 出站授权门控（ct-base 全库统一范式，对齐 ct-advisor scripts/refine_answer.py）
# ---------------------------------------------------------------------------
# 本会话内存已授权端点（随进程重置：同一次脚本运行内多次出站只确认一次）。
_SESSION_AUTHORIZED_ENDPOINTS = set()


def _default_config_path() -> str:
    """config.json 默认路径（技能根 config/）。"""
    here = Path(__file__).resolve().parent.parent  # adapters/ -> 技能根
    return str(here / "config" / "config.json")


def _load_auto_approve_endpoints(config_path: str) -> set:
    """从 config.json 加载 auto_approve_endpoints 白名单。"""
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        return set(cfg.get("auto_approve_endpoints", []) or [])
    except Exception:
        return set()


def _check_outbound_authorization(endpoint: str, config_path: str = None) -> bool:
    """出站授权检查：返回 True 放行，False 拦截（不发送）。

    语义（ct-base）：
      - 命中本会话内存 / config.json 白名单（作者预置公共端点）→ True，永不弹确认；
      - 否则 stderr 输出 AUTH-BLOCK + 全库统一确认提示，返回 False。
    白名单写入须由用户确认触发（agent 引导、不代写 config.json）。
    """
    if endpoint in _SESSION_AUTHORIZED_ENDPOINTS:
        return True
    cfg_path = config_path or _default_config_path()
    if endpoint in _load_auto_approve_endpoints(cfg_path):
        return True
    # 一次性出站授权确认：强制走 i18n 单语输出（ct-base language_policy §首次使用与一次性运行期提示）。
    # 主路径经 t("auth.coze_outbound") 取词（单一事实来源 scripts/i18n.py），
    # 仅在 i18n 不可导入（测试环境缺 scripts 路径）时退化为英文安全提示，绝不中英双显/硬编码。
    if _HAS_I18N:
        prompt = _i18n_t("auth.coze_outbound", endpoint=endpoint)
    else:
        prompt = (
            "[ct-samplesize] outbound to %s requires user confirmation. "
            "Only trial-design parameters (no personal data) are sent; "
            "declining disables cloud computation." % endpoint
        )
    sys.stderr.write(
        "[ct-samplesize][AUTH-BLOCK] outbound to %s requires user confirmation.\n"
        "%s\n" % (endpoint, prompt)
    )
    return False


def _authorize_endpoint(endpoint: str, config_path: str = None) -> None:
    """（供 agent 引导用户确认后调用）把端点加入会话内存授权。"""
    _SESSION_AUTHORIZED_ENDPOINTS.add(endpoint)


# ---------------------------------------------------------------------------
# payload 脱敏（ct-base：出站 payload 发送前剥离 PII；日志绝不回显明文）
# ---------------------------------------------------------------------------
# 注意（2026-08-19 修复）：原实现用 \b 边界，Python 把中文字符视为 \w，
# "身份证<18位>" 中 "证" 与数字之间无 \b → 身份证/手机号永不匹配。
# 改为数字/字母数字负向断言（对中文相邻文本同样生效）：
#   ID    18位（17数字+X/x）；先于 PHONE 匹配，防止手机号模式吞身份证子串
#   PHONE 大陆手机号
#   EMAIL 邮箱（ASCII 边界，避免吞并相邻中文）
_PII_PATTERNS = [
    (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "<ID>"),               # 身份证号
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "<PHONE>"),             # 大陆手机号
    (re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+(?![A-Za-z0-9])"), "<EMAIL>"),  # 邮箱
]


def sanitize(obj):
    """递归剥离 PII（身份证 / 手机号 / 邮箱），返回脱敏副本（不修改原对象）。"""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, str):
        for pat, repl in _PII_PATTERNS:
            obj = pat.sub(repl, obj)
        return obj
    return obj


# ---------------------------------------------------------------------------
# 端点 / token / locale 解析
# ---------------------------------------------------------------------------
def _resolve_token() -> str:
    """取 coze Bearer token：env(CTSS_COZE_TOKEN) > 内嵌公共 blob。"""
    env = os.environ.get("CTSS_COZE_TOKEN")
    if env:
        return env
    if _embedded_get_token is not None:
        return _embedded_get_token()
    return ""


def _resolve_endpoint() -> str:
    """取 coze 端点：env(CTSS_COZE_ENDPOINT/COZE_ENDPOINT) > 内嵌公共常量。"""
    env = os.environ.get("CTSS_COZE_ENDPOINT") or os.environ.get("COZE_ENDPOINT")
    if env:
        return env
    if _embedded_get_endpoint is not None:
        return _embedded_get_endpoint()
    return ""


def _current_locale() -> str:
    """推导当前界面语言（zh / en），供 coze 端本地化 narrative 与授权提示。

    优先级：
      1. CTSS_LOCALE 环境变量（zh/en，显式强制切换——中文 Windows 上
         is_chinese_os 恒为 True 无法靠 LANG 覆盖，此为 CLI 层强制手段）
      2. i18n.is_chinese_os()（系统 locale 检测）
    失败回退 en，避免阻塞主流程（i18n 不可导入多为测试环境缺 scripts 路径）。
    """
    _v = os.environ.get("CTSS_LOCALE", "").strip().lower()
    if _v in ("zh", "zh_cn", "zh-cn", "cn"):
        return "zh"
    if _v in ("en", "en_us", "en-us"):
        return "en"
    try:
        from i18n import is_chinese_os
        return "zh" if is_chinese_os() else "en"
    except Exception:
        return "en"


# 本地编排控制字段，不进入发往 coze 的请求参数
_PARAM_EXCLUDE = frozenset({
    "yes", "dry_run", "show_code", "install_all_packages", "test",
    # 曲线序列/效应量列表走 curve_* 协议（R 端 run_task.R 曲线分支消费）
    "n_seq", "power_seq", "plot_effects", "effect_seq",
    # 三类新图形开关：dist_plot / power_time_seq / heatmap
    "dist_plot", "power_time_seq", "heatmap",
})


# 契约索引缓存（tests/coze_cases/_contract_index.json 的 required 字段 = 每 test 所需参数白名单）
_CONTRACT_REQUIRED_CACHE = None
_CONTRACT_LOAD_FAILED = False


def _load_contract_required(test):
    """从 _contract_index.json 加载该 test 的 required 参数白名单（单一真相源）。

    返回 frozenset；未登记/契约缺失 → 空 frozenset（调用方退化为发送全部非 None 字段）。
    """
    global _CONTRACT_REQUIRED_CACHE, _CONTRACT_LOAD_FAILED
    if _CONTRACT_REQUIRED_CACHE is not None or _CONTRACT_LOAD_FAILED:
        if _CONTRACT_REQUIRED_CACHE is None:
            return frozenset()
        return _CONTRACT_REQUIRED_CACHE.get(test, frozenset())
    _CONTRACT_REQUIRED_CACHE = {}
    try:
        idx_path = (Path(__file__).resolve().parent.parent
                    / "tests" / "coze_cases" / "_contract_index.json")
        data = json.loads(Path(idx_path).read_text(encoding="utf-8"))
        for entry in data.get("tests", []):
            _CONTRACT_REQUIRED_CACHE[entry["test"]] = frozenset(entry.get("required", []))
    except Exception:
        _CONTRACT_LOAD_FAILED = True
    return _CONTRACT_REQUIRED_CACHE.get(test, frozenset()) if _CONTRACT_REQUIRED_CACHE else frozenset()


def build_params(test, args, ctx):
    """把 args + ctx 序列化为 JSON 友好的请求参数。

    仅发送「本 test 实际需要」的参数，避免把 argparse 全家族默认值（varcorr/sigma/
    nsim/theta0/cv/design/ve_*/prior_a0/prob_*/n_doses/target_dlt/win_ratio_theta/...）
    一锅炖进 params（这些无关默认值虽被 R 端 %||% 忽略，但会让飞书 querystr 看起来像
    「全参数扫描」，无法区分真实请求与测试）。白名单取自 tests/coze_cases/_contract_index.json
    的 required 字段（与 CLI choices / R 引擎 dispatch 三者一致的单一真相源）。

    发送集合 = 该 test 的 required 参数（非 None）+ 通用参数 alpha + 模式关键参数
    （求 n → power；求 power → nobs）+ 派生量（solve_for_power/alt/d_val）+ 曲线参数
    （curve_*，来自 --n_seq/--power_seq/--plot_effects）。
    """
    ns = vars(args)
    required = _load_contract_required(test)
    params = {}
    if required:
        for k in required:
            if k in ns and ns[k] is not None:
                params[k] = ns[k]
        # 通用参数：alpha 几乎被全部 R 分支消费；argparse 默认 0.05，总是随请求带上
        alpha = ns.get("alpha")
        if alpha is not None:
            params.setdefault("alpha", alpha)
        # 模式关键参数：求样本量需要 target power；求效能需要 nobs
        if ctx.get("solve_for_power"):
            nobs = ns.get("nobs")
            if nobs is not None:
                params["nobs"] = nobs
        else:
            params["power"] = ns.get("power") or 0.8
    else:
        # 契约缺失/未登记 → 退化为原行为（发送全部非 None、非控制字段），保证不丢参
        for k, v in ns.items():
            if k in _PARAM_EXCLUDE:
                continue
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool, list)):
                params[k] = v
    # 派生量
    params.update({
        "solve_for_power": ctx.get("solve_for_power", False),
        "alt": ctx.get("alt", "two.sided"),
        "d_val": ctx.get("d_val"),
    })
    # 曲线参数映射（CLI 名 → coze 端 curve_* 协议，R 端 run_task.R 曲线分支消费）
    for cli_key, coze_key in (("n_seq", "curve_n_seq"),
                              ("power_seq", "curve_power_seq"),
                              ("plot_effects", "curve_effects"),
                              ("effect_seq", "curve_effect_seq"),
                              ("dist_plot", "plot_dist"),
                              ("power_time_seq", "curve_power_time_seq"),
                              ("heatmap", "curve_heatmap")):
        val = ns.get(cli_key)
        if val:
            params[coze_key] = val
    return params


def _fill_external_svgs(parsed, timeout=30):
    """统一 manifest 重组入口（对齐 meta-analysis 2026-08-28）：
    优先走**新契约**：若响应含 `_coze_manifest`（coze 端把超 4000 的 figures/repro/narrative
    统一移进单个 manifest 文件并挂链接），则 GET manifest → 逐 path 写回原值 →
    重组为原始 JSON（含 content/r 代码/narrative），一次还原、零数据丢失。

    **向后兼容**：无 `_coze_manifest`（旧 coze 响应 / 方案 B）时，走旧契约——
    figures[].url→content、repro.url→r 逐项回填。

    - 超时 / 网络失败 → 保留引用并标记 _*_fetch_failed，绝不抛错中断分析。
    """
    if not isinstance(parsed, dict):
        return parsed
    # 新契约：manifest 单文件重组（优先级最高）
    manifest = parsed.get("_coze_manifest")
    if isinstance(manifest, dict) and manifest.get("storage") == "s3" and manifest.get("url"):
        return _reassemble_from_manifest(parsed, manifest, timeout=timeout)
    # 旧契约（方案 B，向后兼容）：figures[].url → content / repro.url → r
    return _fill_external_svgs_legacy(parsed, timeout=timeout)


def _reassemble_from_manifest(parsed, manifest, timeout=30):
    """按 manifest 重组原始 JSON（对齐 meta-analysis 2026-08-28，ct-samplesize 移植版）：
    coze 端把超 4000 的最大块（figures/repro/narrative）统一移进单个 S3 manifest 文件，
    manifest 为 [{path, value}, ...]，主返回体挂 `_coze_manifest = {storage:"s3", url}`。
    此处 GET manifest → 按 path 写回 value → 重组为原始 JSON。

    - path 支持 `figures[i]`（列表下标）、`stats.xxx` 点路径、**以及顶层键**（如 `narrative`）。
    - 写回时若该位置当前仍是 {storage:"s3",type:"block"} 引用（未被本地改动）才覆盖。
    - 超时 / 网络失败 → 保留 manifest 引用并在主返回体标 _manifest_failed，绝不抛错中断。
    - 重组完成后移除 `_coze_manifest`（下游见到的即原始结构）。
    """
    url = manifest.get("url")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            manifest_list = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        parsed["_manifest_failed"] = True
        return parsed
    if not isinstance(manifest_list, list):
        parsed["_manifest_failed"] = True
        return parsed

    def _resolve_target(root, path):
        """返回 (容器, key) 或 (list, idx) 以便写回；找不到返回 None。
        支持 figures[i] / stats.xxx 点路径 / 顶层键（如 narrative）。
        """
        if path.startswith("figures["):
            # figures[i]
            m = path[8:-1]
            if not m.isdigit():
                return None
            idx = int(m)
            figs = root.get("figures")
            if not isinstance(figs, list) or idx >= len(figs):
                return None
            return figs, idx
        if "." in path:
            # stats.a.b 点路径
            parts = path.split(".")
            node = root
            for p in parts[:-1]:
                if not isinstance(node, dict) or p not in node:
                    return None
                node = node[p]
            if not isinstance(node, dict) or parts[-1] not in node:
                return None
            return node, parts[-1]
        # 顶层键（如 narrative）
        if isinstance(root, dict) and path in root:
            return root, path
        return None

    for entry in manifest_list:
        if not isinstance(entry, dict):
            continue
        p = entry.get("path")
        if not p:
            continue
        target = _resolve_target(parsed, p)
        if target is None:
            continue
        container, key = target
        cur = container[key]
        # 仅当仍是外置引用时才写回；已被本地改动为实际内容则跳过
        if isinstance(container, dict):
            is_ref = (isinstance(cur, dict) and cur.get("storage") == "s3"
                      and cur.get("type") == "block")
            if is_ref:
                container[key] = entry.get("value")
        else:  # list
            if isinstance(cur, dict) and cur.get("storage") == "s3" and cur.get("type") == "block":
                container[key] = entry.get("value")
    # 重组完成，移除 manifest 引用（下游见原始结构）
    parsed.pop("_coze_manifest", None)
    return parsed


def _fill_external_svgs_legacy(parsed, timeout=30):
    """旧契约（方案 B，向后兼容）：coze 端把 figures[].content（SVG）与 repro['r']
    （R 复现脚本）外置 S3 并返回 {type,format,storage:"s3",key,url} 引用；按 url 下载回填。

    - 超时 / 网络失败 → 保留 url 并标记 _svg_fetch_failed / _repro_fetch_failed，绝不抛错中断。
    - 已含 content / r（coze 降级内联）或不是 dict → 原样跳过。
    """
    if not isinstance(parsed, dict):
        return parsed
    figs = parsed.get("figures")
    if isinstance(figs, list):
        for fig in figs:
            if not isinstance(fig, dict):
                continue
            if fig.get("url") and not fig.get("content"):
                try:
                    with urllib.request.urlopen(fig["url"], timeout=timeout) as r:
                        fig["content"] = r.read().decode("utf-8")
                except Exception:  # noqa: BLE001
                    fig["_svg_fetch_failed"] = True
    # 方案 B 扩展：R 复现脚本外链回填（repro.url → repro.r）
    repro = parsed.get("repro")
    if isinstance(repro, dict) and repro.get("url") and not repro.get("r"):
        try:
            with urllib.request.urlopen(repro["url"], timeout=timeout) as r:
                repro["r"] = r.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            repro["_repro_fetch_failed"] = True
    return parsed


def _fetch_full_json(parsed, timeout=30):
    """新契约（2026-08-29）：coze 把 R 引擎生成的完整信封整体写入单个 S3 文件，
    内联挂 `_coze_full = {storage:"s3", url}`。本地经 url 下载完整 JSON 作为分析源
    （含 figures/repro，零删减）。内联的轻量删减版（无 figures/repro）仅用于飞书日志
    与老版本技能兼容，本地分析不使用。

    返回完整 dict；下载失败 / 无链接 / 非 dict → 返回 None（调用方降级到旧契约或内联）。
    """
    if not isinstance(parsed, dict):
        return None
    full = parsed.get("_coze_full")
    if not (isinstance(full, dict) and full.get("storage") == "s3" and full.get("url")):
        return None
    try:
        with urllib.request.urlopen(full["url"], timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        parsed["_full_fetch_failed"] = True
        return None
    if not isinstance(data, dict):
        parsed["_full_fetch_failed"] = True
        return None
    data.pop("_coze_full", None)
    return data


def _mock_envelope(test, params, mode, return_r_code):
    """本地 mock：演示用样例信封（v5 结构：status/stats/narrative/figures）。"""
    sample_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="160">'
        '<rect width="100%%" height="100%%" fill="#fafafa"/>'
        '<text x="10" y="30" font-family="sans-serif" font-size="14">'
        'MOCK power curve (%s)</text>'
        '<polyline points="20,140 120,80 300,30" fill="none" stroke="#c0392b" stroke-width="2"/>'
        '</svg>' % test
    )
    env = {
        "status": "ok",
        "stats": {"test": test, "mode": mode, "note": "mock"},
        "narrative": (
            "MOCK coze response for test=%s (mode=%s).\n"
            "真实端点就绪后此处返回 R 端算出的数值与叙述。" % (test, mode)),
        "figures": [
            {"format": "svg", "content": sample_svg,
             "caption": "Mock power curve (%s)" % test}
        ],
        "warnings": ["MOCK 响应，非真实计算"],
        "notes": "",
        "repro": {"r": "# MOCK R code for %s" % test, "r_version": "mock",
                  "packages": {}},
    }
    return env


def _urlopen_with_proxy_fallback(req, connect_timeout=15, read_timeout=None):
    """HTTP POST + Windows 系统代理残留直连重试（ct-base 出站容错）。

    ⚠️ 关键修正（2026-08-29，对齐 meta-analysis）：
    旧实现 `http.client.HTTPSConnection(host, timeout=15)` 的 timeout 实际作用于
    **所有** socket 操作（connect 与 recv 共享同一超时）——注释里"读取不设限"是
    **错误**的。coze serverless 冷启动常 >15s，导致**读取响应阶段**被 15s 杀掉，
    表现为"每次都 15s 无应答"。meta-analysis 用 `urllib.urlopen(timeout=600)` 因此无此问题。

    修正方案：把 connect 与 read 拆成两个独立超时——
      - connect_timeout=15：连接握手失败快速报错（主机不可达时不空等）；
      - read_timeout（默认 600s，可由 CTSS_COZE_READ_TIMEOUT 覆盖）：允许冷启动
        与大规模 Monte-Carlo 计算的长时间响应读取，不被中途杀掉。
    实现：conn.request() 内部完成 connect+send（受 connect_timeout 约束），
    之后把底层 socket 超时改为 read_timeout，再 getresponse()/read()（受 read_timeout 约束）。

    返回对象实现 `.read()` 与上下文管理器，`call()` 的
    `with ... as resp: resp.read()` 契约保持不变。
    """
    import http.client

    if read_timeout is None:
        try:
            read_timeout = float(os.environ.get("CTSS_COZE_READ_TIMEOUT", "600"))
        except (TypeError, ValueError):
            read_timeout = 600.0

    def _conn():
        # connect 阶段受 connect_timeout 约束（主机不可达时快速失败，不空等 600s）。
        if req.type == "https":
            return http.client.HTTPSConnection(req.host, timeout=connect_timeout)
        return http.client.HTTPConnection(req.host, timeout=connect_timeout)

    def _do(conn):
        body = req.data if hasattr(req, "data") else None
        headers = dict(req.headers) if hasattr(req, "headers") else {}
        conn.request(req.get_method(), req.selector, body=body, headers=headers)
        # 连接已建立、请求已发出 → 把底层 socket 超时从 connect 改为 read 长超时，
        # 避免 coze 冷启动 / 长时间计算被 15s 杀掉（对齐 meta-analysis 的 600s 策略）。
        if getattr(conn, "sock", None) is not None:
            conn.sock.settimeout(read_timeout)
        return conn.getresponse()

    for attempt in (1, 2):
        conn = _conn()
        try:
            resp = _do(conn)
            return resp
        except (http.client.HTTPException, OSError, socket.error) as e:
            conn.close()
            # 首次失败若是 Windows 系统代理残留（10061/10060/11004），直连重试一次；
            # 计算请求幂等，重试无副作用。
            winerr = getattr(e, "winerror", None) or getattr(getattr(e, "reason", None), "winerror", None)
            errno = getattr(e, "errno", None) or getattr(getattr(e, "reason", None), "errno", None)
            if attempt == 1 and (winerr in (10061, 10060, 11004) or errno in (10061, 10060, 11004)):
                continue
            # 非代理残留错误 → 包装为与 urllib 一致的异常语义上抛
            raise urllib.error.URLError(reason=e)


def call(test, params, mode, return_r_code, locale=None, resolved_spec=None):
    """调用 coze 服务，返回 R 引擎信封 dict（重构 v5 协议）。

    模式（优先级从高到低）：
      - CTSS_COZE_MOCK=1 → 本地 mock 信封（演示/测试；无出站、不走授权门控）
      - CTSS_COZE_ENDPOINT / COZE_ENDPOINT 或内嵌端点 → 真实 HTTP POST（urllib，无第三方依赖）
      - 均未设置 → 抛错提示配置端点

    出站授权（ct-base §5）：真实发送前经 _check_outbound_authorization 门控；
    未授权 → stderr AUTH-BLOCK + 确认提示，**不发送**、返回 None（授权不阻断流程，
    由调用方提示用户）。发往端点的 payload 经 sanitize() 剥离 PII。
    """
    # mock 显式优先：设置了 mock 绝不联网、不走授权门控（2026-08-19 修复：
    # 原实现把 mock 分支放在 endpoint 之后，内嵌端点恒非空导致 mock 成为死代码）
    if os.environ.get("CTSS_COZE_MOCK") in ("1", "true", "yes"):
        return _mock_envelope(test, params, mode, return_r_code)
    endpoint = _resolve_endpoint()
    if endpoint:
        # ── 出站授权门控（ct-base 全库统一）──────────────────────────────
        if not _check_outbound_authorization(endpoint):
            return None  # AUTH-BLOCK：不发送，调用方提示用户
        token = _resolve_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer %s" % token
        # 发送前脱敏（剥离 PII）；脱敏副本用于发送，原 params 不受影响
        payload = json.dumps({
            "test": test, "params": sanitize(params), "mode": mode,
            "return_r_code": return_r_code,
            "locale": locale or _current_locale(),
            "query_origin": _compute_query_origin(),
            "resolved_spec": resolved_spec or {
                "test": test, "mode": mode, "params": sanitize(params)
            },
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            endpoint, data=payload, headers=headers, method="POST")
        # coze 调用并发限流（ct-base §20.10）：相邻两次 coze POST 间隔 ≥1 秒，
        # 防触发 429 频控；间隔秒数由 COZE_META_MIN_INTERVAL 覆写。
        _acquire_rate_limit()
        try:
            # 超时：取消【读取】限制（Monte-Carlo / 大规模模拟可能远超 180s），
            # 仅保留 15s 连接握手保护，避免端点不可达时 agent 永久阻塞。
            # 远端 main.py TIMEOUT_SECONDS=900 为硬上限，read 永不越过该边界。
            with _urlopen_with_proxy_fallback(req) as resp:
                outer = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            # 只打异常类型 + 端点（绝不回显 token / payload）
            raise RuntimeError("coze 调用失败（%s）: %s" % (endpoint, e))
        # v5：解析外层 result（R 引擎信封 JSON 字符串）；兼容旧直接信封
        result_str = outer.get("result") if isinstance(outer, dict) else None
        if isinstance(result_str, str) and result_str.strip().startswith("{"):
            try:
                parsed = json.loads(result_str)
            except ValueError:
                return outer
            # 新契约（2026-08-29）：完整 JSON 存 S3，内联仅轻量删减版。
            # 本地优先经 _coze_full 下载完整数据做分析（含 figures/repro，零删减）；
            # 失败 / 无链接则降级到旧契约（manifest / figures[].url）或直接使用内联删减版。
            full = _fetch_full_json(parsed, timeout=30)
            if full is not None:
                return full
            return _fill_external_svgs(parsed)
        if isinstance(outer, dict):
            return _fill_external_svgs(outer)
        return {"status": "error", "notes": "coze 返回空/非对象响应"}
    raise RuntimeError(
        "coze 端点未配置：请设置 CTSS_COZE_ENDPOINT（真实），"
        "或 CTSS_COZE_MOCK=1（本地演示）。")


class CozeBackend(ComputeBackend):
    name = "coze"
    # coze 为远程纯计算、无本地副作用 → 不强制 --yes；--dry-run 仍只预览不发送。
    requires_confirmation = False

    def preview(self, test, args, ctx):
        """--dry-run / --show-code 时展示将要发往 coze 的请求信封（脱敏后）。"""
        if not (ctx.get("dry_run") or ctx.get("show_code")):
            return None
        mode = "power" if ctx.get("solve_for_power") else "n"
        params = build_params(test, args, ctx)
        return json.dumps({
            "endpoint": _resolve_endpoint() or "(mock)",
            "test": test,
            "mode": mode,
            "return_r_code": ctx.get("return_r_code", False),
            "locale": ctx.get("locale") or _current_locale(),
            "query_origin": _compute_query_origin(),
            "params": sanitize(params),
            "resolved_spec": {"test": test, "mode": mode, "params": sanitize(params)},
        }, ensure_ascii=False, indent=2)

    def compute(self, test, args, ctx):
        params = build_params(test, args, ctx)
        mode = "power" if ctx.get("solve_for_power") else "n"
        # P3：resolved_spec 契约增强——本次完整语义快照，远端可选消费（补参/校验）。
        resolved_spec = {"test": test, "mode": mode, "params": sanitize(params)}
        env = call(test, params, mode, ctx.get("return_r_code", False),
                   locale=ctx.get("locale") or _current_locale(),
                   resolved_spec=resolved_spec)
        # AUTH-BLOCK：未授权不发送，提示用户（授权不阻断流程）
        if env is None:
            raise RuntimeError(
                "出站未授权：本次未发送到云端计算。"
                "若同意发送，请确认后将端点加入 config/config.json 的 "
                "auto_approve_endpoints（或重跑本命令）。")
        # v5 信封：status/stats/narrative/warnings/notes/repro
        if not isinstance(env, dict):
            raise RuntimeError("coze 返回非对象响应")
        # ── 契约漂移检测 + 结构自适应兼容（ct-base §20.9 单入口 _assess_contract）──
        # 仅结构/数据内容不一致触发提醒：结构别名自愈兼容，无需比对版本号。
        # 用户可见提示统一只在渲染层 HTML 横幅（_needs_upgrade/_contract_drift 驱动），
        # 不写 stderr、不污染 narrative/notes（零噪音原则）。
        env, drift_notes, needs_upgrade = _assess_contract(env)
        # 自适应兼容：缺字段补默认，保证下游不 KeyError
        env.setdefault("stats", {})
        env.setdefault("narrative", "")
        env.setdefault("figures", [])
        env.setdefault("warnings", [])
        env.setdefault("notes", "")
        env.setdefault("repro", {})
        # 机器可读标记写回信封（rendering 横幅消费；非用户提示）
        env["_needs_upgrade"] = needs_upgrade
        if drift_notes:
            env["_contract_drift"] = drift_notes
        # 契约 §5：coze 出错可返回 {"error": {...}}；原样呈现 message
        err = env.get("error")
        if err:
            msg = err.get("message") or err.get("code") or "coze 端返回未知错误"
            raise RuntimeError("coze 计算失败: %s" % msg)
        status = env.get("status")
        if status in ("error", "unknown_task"):
            raise RuntimeError("coze 计算失败: %s" % (env.get("notes") or status))
        stats = env.get("stats") or {}
        repro = env.get("repro") or {}
        # 截断告警（coze 返回体超 4000 字符、已丢部分 stats 子块；narrative 优先外置故鲜触发）
        truncated = env.get("_coze_truncated")
        text = env.get("narrative", "") or ""
        meta = dict(stats)
        if truncated:
            sys.stderr.write(
                "\n[ct-samplesize] 注意：coze 返回体超 4000 字符，"
                "已截断部分 stats 子块：%s\n" % truncated)
            meta["_coze_truncated"] = truncated
        # 契约漂移标记：透出到 meta（rendering 经 res.meta 读取，写回报告横幅）
        meta["_needs_upgrade"] = needs_upgrade
        if drift_notes:
            meta["_contract_drift"] = drift_notes
        return Result(
            text=text,
            figures=[Figure(f.get("format", "svg"), f.get("content", ""),
                            f.get("caption", "")) for f in env.get("figures", [])],
            r_code=repro.get("r") if ctx.get("return_r_code") else None,
            r_result=stats,
            meta=meta,
            backend=self.name,
        )
