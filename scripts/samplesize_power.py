#!/usr/bin/env python3
"""
Clinical Trial Sample Size & Power Calculator — v5.0.2

Architecture (v5):
- Default authoritative engine = remote coze R compute service (CozeBackend).
  Only trial-design params are sent (HTTP POST, no shell, no local R).
- v5 removed the local pure-Python fallback (LocalPythonBackend) and all
  third-party compute deps (statsmodels / numpy / scipy no longer required).
  select_backend() returns ONLY CozeBackend; coze unreachable → error, no fallback.
- Local R backend (LocalRBackend, in adapters/coze/ct_r_lib/) is dev/transition only and is
  NOT shipped in the published package.
- Safe by default: --dry-run previews the exact coze request envelope; coze is
  a stateless compute service, so no local code is ever executed. The legacy
  --yes gate applies only to the optional local-R backend.
- Every user string that reaches server-side R is validated against a strict
  allowlist, so it can NEVER break out of an R string literal.
- Input args validated against strict allowlists regardless of backend.

Test types (49 total):
  Core: ttest_ind, ttest_paired, anova, proportion_one, proportion_two,
        non_inferiority, equivalence, be_tost, mixed_model, roc, poisson,
        bland_altman, cluster, vaccine_efficacy, multiple_endpoints,
        bayesian, dose_escalation
  New in v3.3: win_ratio, must_win, historical_controls, mams,
        conditional_power, ni_survival, superiority_margin, assurance,
        dunnett, mediation, group_sequential, adaptive, survival_exact
  New in v3.5 (PASS-survival): survival_equivalence, survival_superiority,
        cox_covariate, survival_one_sample, competing_risks,
        recurrent_events, survival_historical
  New in v3.6 (PASS Group-Sequential, rpact-backed): group_sequential
        (upgraded to rpact exact two-sample means), gsd_proportion,
        gsd_survival, gsd_hazard, gsd_poisson; real spending functions
        (OF/Pocock/WT/HSD-gamma/Kim-DeMets) + non-binding futility bounds
"""
import argparse, sys, os, io, tempfile, re, json, time
from i18n import t
from compute_backend import select_backend, Result, Figure

# P1-C: local Monte-Carlo verification of an analytic sample-size solution
# (power ±2pp / TIE ±0.5pp). Independent implementation — does NOT reuse the
# analytic formulas, so a wrongly-derived n is caught, not rubber-stamped.
try:
    from verify import run_verify as _verify_run, format_report as _verify_fmt
except Exception:  # pragma: no cover — verify.py always ships alongside
    _verify_run = None
    _verify_fmt = None

# ── E1/E2: 本地确定性 NL 路由 + 参数别名解析（零 LLM，仅作 coze LLM 之前的快速预路由）──
# 同目录 import（脚本可直接运行，也兼容从其他 cwd 经 subprocess 调用）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
try:
    from classify_test import classify as _nl_classify
    from param_aliases import extract_parameters as _nl_extract
    _NL_AVAILABLE = True
except Exception:  # pragma: no cover — 缺模块时降级为「无 --nl 能力」
    _NL_AVAILABLE = False


# ═════════════════════════════════════════════════════════════════════════════
# 图形产物落盘与展示（coze 可能回传 SVG / HTML / PNG）
# ═════════════════════════════════════════════════════════════════════════════

# ── 输入白名单校验（编排层职责：无论送往 coze 还是本地 R，都先卡死危险字符）──
_SAFE_TOKEN_RE = re.compile(r'^[A-Za-z0-9_\-]+$')
_SAFE_PATH_RE = re.compile(r'^[A-Za-z0-9_.\- /\\:一-鿿]+$')


def _validate_token(name, value):
    """Reject categorical string args that could break out into generated code."""
    if value is None:
        return value
    if not _SAFE_TOKEN_RE.match(value):
        raise ValueError(
            "Invalid %s=%r: only [A-Za-z0-9_-] allowed "
            "(no quotes, semicolons or parentheses)." % (name, value)
        )
    return value


def _validate_path(path):
    """Reject output paths containing characters that could escape a string literal."""
    if path is None:
        return None
    if not _SAFE_PATH_RE.match(path):
        raise ValueError(
            "Unsafe output path %r: only letters, digits, spaces and ._-:/\\ "
            "are allowed (no quotes, semicolons or parentheses)." % path
        )
    return path


_FIG_EXT = {"svg": ".svg", "html": ".html", "png": ".png"}

# ── 渲染计时与超阈值提示（ct-base §19.10，全库统一）──
# 界面浏览器渲染无法在 agent 侧精确计时，用 SVG 体量作代理；超阈值生成 render_hint
RENDER_SVG_THRESHOLD = 30.0       # 本地渲染处理耗时上限（秒）
RENDER_SVG_KB_THRESHOLD = 200.0   # 单图/合计 SVG 体量上限（KB）


def _outputs_dir() -> str:
    """图形落盘目录：优先 CTSS_OUTPUT_DIR，其次当前工作目录下的 outputs/。"""
    d = os.environ.get("CTSS_OUTPUT_DIR") or os.path.join(os.getcwd(), "outputs")
    os.makedirs(d, exist_ok=True)
    return d


#: 契约缺失时的默认出图集合（与 v5.3.1 硬编码一致；契约就绪后由 _auto_curve_tests 取代）
_FALLBACK_AUTO_CURVE_TESTS = frozenset({
    "ttest_ind", "ttest_paired", "ttest_one",
    "proportion_one", "proportion_two",
})
_AUTO_CURVE_TESTS_CACHE = None


def _auto_curve_tests() -> frozenset:
    """从 tests/coze_cases/_contract_index.json 读取 default_curve=true 的 test 集合。

    单一真相源（v5.3.2）：每种检验方法「默认是否自动出曲线」由契约的
    default_curve 字段分别配置（改契约即改默认出图，无需改代码）；
    契约缺失 / 未登记字段时回退硬编码集合（与前版本行为一致）。
    """
    global _AUTO_CURVE_TESTS_CACHE
    if _AUTO_CURVE_TESTS_CACHE is not None:
        return _AUTO_CURVE_TESTS_CACHE
    try:
        idx_path = (Path(__file__).resolve().parent.parent
                    / "tests" / "coze_cases" / "_contract_index.json")
        data = json.loads(Path(idx_path).read_text(encoding="utf-8"))
        s = frozenset(
            t["test"] for t in data.get("tests", [])
            if t.get("default_curve") is True
        )
        _AUTO_CURVE_TESTS_CACHE = s or _FALLBACK_AUTO_CURVE_TESTS
    except Exception:  # noqa: BLE001 - 契约缺失时回退硬编码
        _AUTO_CURVE_TESTS_CACHE = _FALLBACK_AUTO_CURVE_TESTS
    return _AUTO_CURVE_TESTS_CACHE


def _resolve_figure_mode(explicit=None) -> str:
    """出图模式（ct-base §19.9）：svg_inline 默认；png_file 用 cairosvg 转位图。

    优先级：显式参数 > 环境变量 CTSS_FIGURE_MODE > 默认 svg_inline。
    """
    mode = (explicit or os.environ.get("CTSS_FIGURE_MODE") or "svg_inline").lower()
    return mode if mode in ("svg_inline", "png_file") else "svg_inline"


def render_figures(figures, test: str, figure_mode=None):
    """把后端回传的图形写入磁盘，并打印标记供宿主渲染。

    标记格式（宿主 agent 据此调用可视化 / 文件展示能力）：
        __FIGURE__ <format> <abs_path> caption="..."
        __SVG_WIDGET__ <html fragment>   # SVG 图：ct-base §19 内联渲染（宿主直接内嵌对话流）
        __RENDER_HINT__ <text>           # 超阈值提醒（ct-base §19.10），agent 必须在回复中体现

    出图模式（figure_mode，ct-base §19.9）：
        - svg_inline（默认）：__SVG_WIDGET__ 内联 + 落盘 .svg
        - png_file：cairosvg 转 PNG 落盘，emit __FIGURE__ png（不内联 SVG；需 cairosvg，
          未安装时优雅降级回 svg_inline 并提示）

    渲染计时与超阈值提示（ct-base §19.10）：
        - render_elapsed_seconds：本地渲染阶段耗时（拿到 SVG → widget/PNG 就绪）
        - render_svg_kb：所有 SVG 字节合计（KB），界面渲染无法精确计时，用此作代理
        - 任一超阈值（>30s / >200KB）生成 __RENDER_HINT__，建议切换 png_file
    """
    if not figures:
        return
    outdir = _outputs_dir()
    mode = _resolve_figure_mode(figure_mode)
    svg_figs = []
    _svg_paths = []
    _svg_kb = 0.0
    _t0 = time.time()
    for i, fig in enumerate(figures, 1):
        fmt = (fig.format or "svg").lower()
        ext = _FIG_EXT.get(fmt, ".txt")
        path = os.path.join(outdir, "ctss_%s_%d%s" % (test, i, ext))
        content = fig.content or ""
        if fmt == "png" and not content.lstrip().startswith("<"):
            import base64
            with open(path, "wb") as f:
                f.write(base64.b64decode(content))
        else:
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(content)
        if fmt == "svg":
            svg_figs.append({"svg": content, "type": fig.caption or "ct-samplesize 图"})
            _svg_paths.append(path)
            _svg_kb += len(content.encode("utf-8")) / 1024.0
        # 2026-08-28 设计修订（用户定）：对话流不展示单张图形，仅 HTML 报告全量展示。
        # __FIGURE__ svg/png（会触发宿主内联展示）默认关闭，仅保留落盘供归档/下载；
        # 宿主如需逐图内联展示，设 CTSS_INLINE_WIDGET=1 恢复。
        if os.environ.get("CTSS_INLINE_WIDGET") == "1":
            print('__FIGURE__ %s %s caption="%s"' % (fmt, path, (fig.caption or "").replace('"', "'")))
    # ct-base §19：SVG 内联渲染（复用统一 adapters/rendering.py 管线）
    if svg_figs:
        try:
            _skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            _adapters_dir = os.path.join(_skill_root, "adapters")
            for _p in (_skill_root, _adapters_dir):
                if _p not in sys.path:
                    sys.path.insert(0, _p)
            from rendering import build_figure_widget, svg_to_png  # type: ignore  # adapters/rendering.py

            if mode == "png_file":
                # 本地 cairosvg 转 PNG（同一处理链：strip clip → fix xml → bbox → viewBox → 光栅化）
                for j, f in enumerate(svg_figs, 1):
                    try:
                        png_path = os.path.join(outdir, "ctss_%s_%d.png" % (test, j))
                        svg_to_png(f["svg"], png_path, scale=2.0)
                        if os.environ.get("CTSS_INLINE_WIDGET") == "1":
                            print('__FIGURE__ png %s caption="%s"' % (png_path, (f.get("type") or "").replace('"', "'")))
                    except Exception as e:  # noqa: BLE001 - cairosvg 缺失/失败 → 优雅降级
                        print("# png_file 转换失败，降级 svg_inline: %s" % e)
                        mode = "svg_inline"
                        break
            if mode == "svg_inline":
                # 2026-08-28 设计修订（用户定）：对话流不再内联 SVG 图形，
                # 图形展示完全交给 render_html_report 全量输出（HTML 报告）。
                # 这里只落盘 SVG 源文件 + __FIGURE__ svg 标记供下载/归档；
                # 若宿主仍需对话流内联，可设 CTSS_INLINE_WIDGET=1 恢复 __SVG_WIDGET__。
                if os.environ.get("CTSS_INLINE_WIDGET") == "1":
                    titles = [f.get("type") or "图 %d" % (j + 1) for j, f in enumerate(svg_figs)]
                    html = build_figure_widget(svg_figs, titles)
                    print("__SVG_WIDGET__ " + html)
                # SVG 源文件供下载（用户在对话流仅看到报告入口，文件在此持久化）
                if _svg_paths:
                    print("# SVG 图形已落盘（全量展示见 HTML 报告）: %s" % ", ".join(_svg_paths))
        except Exception as e:  # noqa: BLE001 - 渲染失败不阻断主流程
            print("# __SVG_WIDGET__ 生成失败: %s" % e)

    # ── 渲染计时与超阈值提示（ct-base §19.10）──
    _elapsed = round(time.time() - _t0, 3)
    _hint = None
    if mode == "svg_inline":
        reasons = []
        if _elapsed > RENDER_SVG_THRESHOLD:
            reasons.append("本地渲染处理耗时 %.0fs（> %.0fs 阈值）" % (_elapsed, RENDER_SVG_THRESHOLD))
        if _svg_kb > RENDER_SVG_KB_THRESHOLD:
            reasons.append("SVG 体量 %.0fKB（> %.0fKB，界面渲染/滚动可能明显变慢）" % (_svg_kb, RENDER_SVG_KB_THRESHOLD))
        if reasons:
            _hint = "；".join(reasons) + "。可切换图片文件模式（figure_mode='png_file' / 环境变量 CTSS_FIGURE_MODE=png_file）：本地 cairosvg 转 PNG，界面渲染更快、不占上下文（但变位图）。"
            print("__RENDER_HINT__ " + _hint)
    # 诊断信息（不参与提示，仅供排查）
    print("# render_elapsed_seconds=%.3f render_svg_kb=%.1f figure_mode=%s" % (_elapsed, _svg_kb, mode))


def _curve_svg_from_stats(stats: dict, test: str, target_power: float = None,
                          ref_n: float = None) -> str:
    """coze 端无图时（svglite/cairo 缺失），用曲线数值 stats{x,y,series} 纯 Python 生成 SVG。

    对齐 ct-base §19 内联渲染：700x500、网格线、多系列折线 + 图例、动态轴标签。
    仅标准库，无第三方依赖。
    ★ Power 参考线（2026-08-20）：当 y 轴语义为 Power 且传入 target_power 时，绘制
    红色虚线参考线（与 coze 权威版 svglite 一致），坐标用与数据点相同的 sy() 映射——
    保证参考线、刻度、数据点三者在同一坐标系统内，杜绝错位。
    """
    xs = stats.get("x") or []
    ys = stats.get("y") or []
    series = stats.get("series") or ["curve"]
    if not xs or not ys or len(xs) != len(ys):
        return ""
    xs = [float(v) for v in xs]
    ys = [float(v) for v in ys]
    # ★ 2026-08-30 用户定稿：样本量-把握度曲线统一为 X=样本量 N、Y=把握度 Power（习惯方向）。
    #   若 coze 端返回的是转置数据（x=power∈[0,1]、y=n>1），此处交换回标准方向。
    x_is_power = all(0.0 <= v <= 1.0 for v in xs) and max(ys) > 1.0
    if x_is_power:
        xs, ys = ys, xs
    xlab, ylab = "N", "Power"
    W, H, PAD_L, PAD_R, PAD_T, PAD_B = 700, 500, 70, 30, 30, 55
    PW, PH = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax == xmin:
        xmax = xmin + 1
    if ymax == ymin:
        ymax = ymin + 1
    ymin, ymax = ymin - (ymax - ymin) * 0.05, ymax + (ymax - ymin) * 0.05

    # ★ 参考线（2026-08-30 用户定稿；X=N、Y=Power 标准方向下）：
    #   正向求解（求 n）→ 在「给定 power」处画【水平线】Y=power，交点 X 即所需样本量；
    #   反向求解（求 power）→ 在「给定样本量」处画【竖线】X=n，交点 Y 即对应效能。
    #   与 run_task.R 对齐（forward: abline(h=power) / reverse: abline(v=nobs)）。
    #   forward 由 target_power 标识（传了 target_power 即求 n），reverse 由 ref_n 标识（求 power）。
    ref_power_val = None
    if target_power is not None and ref_n is None:
        rp = float(target_power)
        if ymin - 1e-9 <= rp <= ymax + 1e-9:
            ref_power_val = rp
    ref_n_val = None
    if ref_n is not None:
        rn = float(ref_n)
        if xmin - 1e-9 <= rn <= xmax + 1e-9:
            ref_n_val = rn

    def sx(v):
        return PAD_L + (v - xmin) / (xmax - xmin) * PW

    def sy(v):
        return PAD_T + (ymax - v) / (ymax - ymin) * PH

    colors = ["#c0392b", "#2980b9", "#27ae60", "#8e44ad", "#d35400", "#16a085"]
    # 系列分组（series 与点一一对应；若 series 为标量则整条单系列）
    groups = {}
    for i in range(len(xs)):
        s = str(series[i] if isinstance(series, list) and i < len(series) else (series if not isinstance(series, list) else "curve"))
        groups.setdefault(s, []).append(i)
    paths = []
    legend = []
    for j, (name, idxs) in enumerate(groups.items()):
        col = colors[j % len(colors)]
        pts = " ".join("%.1f,%.1f" % (sx(xs[i]), sy(ys[i])) for i in idxs)
        paths.append(
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round"/>' % (pts, col))
        cx, cy = sx(xs[idxs[-1]]), sy(ys[idxs[-1]])
        legend.append(
            '<rect x="%.1f" y="%.1f" width="14" height="4" fill="%s"/>'
            '<text x="%.1f" y="%.1f" font-size="11" fill="#333">%s</text>'
            % (cx + 8, cy - 2, col, cx + 26, cy + 3, name))
    grid = []
    for g in range(5):
        gy = PAD_T + PH * g / 4
        grid.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#e0e0e0" stroke-width="1"/>'
                    % (PAD_L, gy, W - PAD_R, gy))
        grid.append('<text x="%d" y="%.1f" font-size="10" fill="#888" text-anchor="end">%.2f</text>'
                    % (PAD_L - 6, gy + 3, ymax - (ymax - ymin) * g / 4))
        gx = PAD_L + PW * g / 4
        grid.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#e0e0e0" stroke-width="1"/>'
                    % (gx, PAD_T, gx, H - PAD_B))
        grid.append('<text x="%.1f" y="%d" font-size="10" fill="#888" text-anchor="middle">%.2f</text>'
                    % (gx, H - PAD_B + 14, xmin + (xmax - xmin) * g / 4))
    ref = ""
    # 样本量竖直参考线（reverse 求 power）：x 轴为样本量时，在给定 n 处画蓝色虚线，
    # 直接读出该 n 对应的效能（与 run_task.R abline(v = nobs) 对齐）。
    refn = ""
    if ref_n_val is not None:
        rx = sx(ref_n_val)
        refn = (
            '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#2980b9" '
            'stroke-width="1.2" stroke-dasharray="6,4"/>' % (rx, PAD_T, rx, H - PAD_B)
            + '<text x="%.1f" y="%d" font-size="10" fill="#2980b9" text-anchor="middle" '
              'font-weight="bold">n = %s</text>' % (rx, PAD_T - 4, format(ref_n_val, "g"))
        )
    # 目标把握度水平参考线（forward 求 n，X=N、Y=Power 标准方向）：在「给定 power」处画红色
    # 水平虚线 Y=power，交点 X 即达到该效能所需样本量（与 run_task.R abline(h = power) 对齐）。
    refp = ""
    if ref_power_val is not None:
        ry = sy(ref_power_val)
        refp = (
            '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#c0392b" '
            'stroke-width="1.2" stroke-dasharray="6,4"/>' % (PAD_L, ry, W - PAD_R, ry)
            + '<text x="%d" y="%.1f" font-size="10" fill="#c0392b" text-anchor="end" '
              'font-weight="bold">power = %s</text>' % (PAD_L - 6, ry - 4, format(ref_power_val, "g"))
        )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d">' % (W, H, W, H)
        + '<rect width="100%%" height="100%%" fill="#ffffff"/>'
        + "".join(grid)
        + ref
        + refp
        + refn
        + '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#999" stroke-width="1"/>'
          % (PAD_L, H - PAD_B, W - PAD_R, H - PAD_B)
        + '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#999" stroke-width="1"/>'
          % (PAD_L, PAD_T, PAD_L, H - PAD_B)
        + "".join(paths)
        + "".join(legend)
        + '<text x="%d" y="%d" font-size="13" fill="#333" font-weight="bold">Curve: %s</text>'
          % (PAD_L, PAD_T - 8, test)
        + '<text x="%d" y="%d" font-size="12" fill="#555" text-anchor="middle">%s</text>'
          % (PAD_L + PW / 2, H - 12, xlab)
        + '<text x="18" y="%d" font-size="12" fill="#555" text-anchor="middle" '
          'transform="rotate(-90 18 %d)">%s</text>'
          % (PAD_T + PH / 2, PAD_T + PH / 2, ylab)
        + "</svg>"
    )
    return svg


def render_curve_fallback(meta: dict, test: str, target_power: float = None,
                          ref_n: float = None):
    """coze 端无图但返回曲线数值时，本地生成 SVG 并输出内联标记（ct-base §19）。

    target_power：Power 参考线目标值（默认 None 不画；reverse 场景传 0.8 或用户 --power）。
    ref_n：样本量竖直参考线位置（reverse 求 power 场景传用户输入的 --nobs；None 不画）。
    """
    stats = (meta or {}).get("stats") if isinstance(meta, dict) else None
    if not isinstance(stats, dict):
        stats = meta if isinstance(meta, dict) and ("x" in meta or "series" in meta) else None
    if not stats:
        return
    xs = stats.get("x")
    ys = stats.get("y")
    if not xs or not ys:
        return
    svg = _curve_svg_from_stats(stats, test, target_power=target_power, ref_n=ref_n)
    if not svg:
        return
    outdir = _outputs_dir()
    path = os.path.join(outdir, "ctss_%s_curve.svg" % test)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    # 2026-08-28 设计修订（用户定）：对话流不内联图形，仅 HTML 报告全量展示。
    if os.environ.get("CTSS_INLINE_WIDGET") == "1":
        print('__FIGURE__ svg %s caption="Curve %s"' % (path, test))
    try:
        _skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _adapters_dir = os.path.join(_skill_root, "adapters")
        for _p in (_skill_root, _adapters_dir):
            if _p not in sys.path:
                sys.path.insert(0, _p)
        from rendering import build_figure_widget  # type: ignore  # adapters/rendering.py
        html = build_figure_widget([{"svg": svg, "type": "Curve %s" % test}],
                                   ["Curve %s" % test])
        if os.environ.get("CTSS_INLINE_WIDGET") == "1":
            print("__SVG_WIDGET__ " + html)
        # 2026-08-28 设计修订：图形展示走 HTML 报告（render_html_report 全量），
        # 此处仅提示落盘 SVG 源文件供下载。
        print("# 图形 SVG 已落盘（全量展示见 HTML 报告）: %s" % path)
    except Exception as e:  # noqa: BLE001
        print("# __SVG_WIDGET__ 生成失败: %s" % e)


def build_parser():
    p = argparse.ArgumentParser(description="Clinical Trial Sample Size Calculator v4.0.1")
    p.add_argument("--test", required=False, default=None,
        choices=["ttest_ind","ttest_paired","ttest_one","anova","proportion_one","proportion_two",
                 "proportion_paired","odds_ratio","risk_ratio",
                 "non_inferiority","survival","mixed_model","roc","poisson",
                 "bland_altman","equivalence","be_tost","cluster",
                 "vaccine_efficacy","multiple_endpoints","bayesian","dose_escalation",
                 "win_ratio","must_win","historical_controls","mams",
                 "conditional_power","ni_survival","superiority_margin","assurance",
                 "dunnett","mediation","group_sequential","gsd_proportion","gsd_survival","gsd_hazard","gsd_poisson","gsd_survival_sim","gsd_hazard_sim","adaptive","survival_exact",
                 "survival_equivalence","survival_superiority","cox_covariate",
                 "survival_one_sample","competing_risks","recurrent_events",
                 "survival_historical",
                 "adaptive_simulate"])
    p.add_argument("--nl", default=None,
                   help="自然语言需求（零 LLM 本地确定性解析：自动识别 --test 并提取参数）。"
                        "例：'非劣效生存试验，NI界值1.25，期望HR=1.0，入组12月随访12月'。"
                        "本地仅做快速预路由；置信度低或参数不全时仍会交由 coze LLM 补全（不静默错参）。")
    p.add_argument("--yes", "-y", action="store_true",
                   help="显式确认执行 R 代码（默认 dry-run 安全预览，仅展示代码、不执行）")
    p.add_argument("--dry-run", action="store_true",
                   help="安全预览：仅生成并展示 R 代码、不执行（默认即此模式）")
    p.add_argument("--show-code", action="store_true", default=False,
                   help="执行并展示生成的 R 代码（默认不展示，仅按需提供）")
    # ── Common ──
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--power", type=float, default=0.8, help="目标检验效能 (与 --nobs 互斥)")
    p.add_argument("--nobs", type=int, default=None, help="给定样本量求效能 (与 --power 互斥)")
    p.add_argument("--show-assumptions", action="store_true", default=False,
                   help="打印本次计算的假设清单（显式输入 / 静默默认值 / 合理区间 / 解读风险）后退出，不做求解")
    # ── t-test / ANOVA ──
    p.add_argument("--effect", type=float)
    p.add_argument("--k_groups", type=int, default=2)
    p.add_argument("--side", choices=["one", "two"], default="two",
                   help="检验方向: one=单侧, two=双侧(默认)")
    p.add_argument("--sd", type=float, default=None,
                   help="标准差。提供时 --effect 视为原始均差(Δ), 自动折算 Cohen's d = effect/sd; 否则 --effect 直接作为 d")
    p.add_argument("--ratio", type=float, default=None,
                   help="两组不等例分配比 n2/n1（仅 ttest_ind 用；缺省=1 等例）。提供时 --nobs 视为第一组 n1，n2=nobs*ratio")
    # ── Proportion ──
    p.add_argument("--p1", type=float, default=0.7,
                   help="gsd_proportion 治疗组比例 (difference 模式必填, 默认 0.7)")
    p.add_argument("--p2", type=float, default=0.5,
                   help="gsd_proportion 对照组比例 (difference 模式必填, 默认 0.5)")
    # ── Non-inferiority / Equivalence ──
    p.add_argument("--margin", type=float)
    # ── Survival ──
    p.add_argument("--hazard_ratio", "--hr", type=float)
    # ── Mixed model ──
    p.add_argument("--effect_name", type=str)
    p.add_argument("--varcorr", type=float, default=0.5)
    p.add_argument("--sigma", type=float, default=1.0)
    p.add_argument("--nsim", type=int, default=500)
    # ── ROC ──
    p.add_argument("--auc0", type=float, default=0.5)
    p.add_argument("--auc1", type=float)
    # ── Poisson ──
    p.add_argument("--lambda1", type=float)
    p.add_argument("--lambda2", type=float)
    p.add_argument("--t1", type=float, default=1.0)
    p.add_argument("--t2", type=float, default=1.0)
    # ── Cluster ──
    p.add_argument("--icc", type=float)
    p.add_argument("--m", type=float)
    p.add_argument("--n_indiv", type=float)
    # ── Bland-Altman ──
    p.add_argument("--sd_diff", type=float)
    p.add_argument("--w", type=float)
    # ── Bioequivalence ──
    p.add_argument("--theta0", type=float, default=0.95)
    p.add_argument("--theta1", type=float, default=None,
                   help="BE 等效下界（默认 0.8；与 --theta2 同给；或单给 --margin 自动 1/margin）")
    p.add_argument("--theta2", type=float, default=None,
                   help="BE 等效上界（默认 1.25；与 --theta1 同给；或单给 --margin 自动 margin）")
    p.add_argument("--cv", type=float, default=0.25)
    p.add_argument("--design", type=str, default="2x2")
    # ── Vaccine, Bayesian, multiple endpoints, dose escalation ──
    p.add_argument("--ve_control", type=float, default=0.02)
    p.add_argument("--ve_treatment", type=float, default=0.005)
    p.add_argument("--prior_a0", type=float, default=0.5)
    p.add_argument("--prob_control", type=float, default=0.3)
    p.add_argument("--prob_treatment", type=float, default=0.15)
    p.add_argument("--correlation", type=float, default=0.5)
    p.add_argument("--n_doses", type=int, default=5)
    p.add_argument("--target_dlt", type=float, default=0.33)

    # ═══ NEW v3.3 arguments ═══
    # Win-Ratio
    p.add_argument("--win_ratio_theta", type=float, default=1.5)
    p.add_argument("--n_sim_initial", type=int, default=100)
    p.add_argument("--se_approx", type=float, default=0.0625)
    p.add_argument("--n_sim", type=int, default=1000)
    # Must-Win / Co-Primary
    p.add_argument("--n_endpoints_must", type=int, default=2)
    p.add_argument("--effect_must", type=float, default=0.3)
    p.add_argument("--correlation_must", type=float, default=0.5)
    # Historical Controls
    p.add_argument("--p_control_current", type=float, default=0.3)
    p.add_argument("--historical_response", type=int, default=15)
    p.add_argument("--historical_n", type=int, default=100)
    p.add_argument("--a0_borrowing", type=float, default=0.5)
    # MAMS
    p.add_argument("--n_arms_mams", type=int, default=3)
    p.add_argument("--n_stages_mams", type=int, default=2)
    p.add_argument("--delta_effect", type=float, default=0.3)
    # Conditional Power / SSR
    p.add_argument("--timing", type=float, default=0.5)
    p.add_argument("--observed_effect", type=float, default=0.2)
    p.add_argument("--planned_effect", type=float, default=0.3)
    p.add_argument("--n_completed", type=int, default=100)
    p.add_argument("--n_planned", type=int, default=200)
    # NI Survival
    p.add_argument("--ni_margin_surv", type=float, default=1.25)
    p.add_argument("--hr_expected", type=float, default=1.0)
    p.add_argument("--accrual_time", type=float, default=12)
    p.add_argument("--followup_time", type=float, default=12)
    p.add_argument("--dropout_rate", type=float, default=0.05)
    p.add_argument("--event_rate", type=float, default=0)
    # Superiority Margin
    p.add_argument("--sup_margin", type=float, default=0.05)
    p.add_argument("--sigma_ratio", type=float, default=1.0)
    p.add_argument("--p_control_sup", type=float, default=0.3)
    p.add_argument("--delta_sup", type=float, default=0.15)
    # Assurance
    p.add_argument("--n_sim_assurance", type=int, default=5000)
    # 2026-08-20 统一为先验 Beta(2,2)：默认 None 不发送，R 端 %||% 2 生效（原 CLI 3/7 覆盖了 R 端默认）
    p.add_argument("--shape1_trt", type=float, default=None)
    p.add_argument("--shape2_trt", type=float, default=None)
    p.add_argument("--shape1_ctrl", type=float, default=None)
    p.add_argument("--shape2_ctrl", type=float, default=None)
    p.add_argument("--n_assurance", type=int, default=100)
    # 2026-08-20 修复：默认 0.0 会被 build_params 发送并覆盖 R 端 %||% 0.05 → margin=0 计算错误；
    # 改为 None 不发送，R 端回落 0.05（另有 <=0 防御）
    p.add_argument("--margin_assurance", type=float, default=None)
    # Dunnett
    p.add_argument("--n_groups_dunnett", type=int, default=3)
    p.add_argument("--n_control_dunnett", type=int, default=50)
    p.add_argument("--effect_dunnett", type=float, default=0.4)
    # Mediation
    p.add_argument("--a_path", type=float, default=0.3)
    p.add_argument("--b_path", type=float, default=0.3)
    p.add_argument("--sigma2_m", type=float, default=1.0)
    p.add_argument("--sigma2_y", type=float, default=1.0)
    p.add_argument("--cprime", type=float, default=0.0)
    p.add_argument("--n_sim_mediation", type=int, default=1000)
    # Group Sequential
    p.add_argument("--n_interim", type=int, default=1,
                   help="中期分析次数 (k-1)；总分析次数 kMax = n_interim + 1")
    p.add_argument("--effect_gs", type=float, default=0.4,
                   help="group_sequential 的标准化效应量 (Cohen's d)")
    p.add_argument("--spending_func", type=str, default="OF",
                   choices=["OF", "Pocock", "WT", "HSD", "KimDeMets"],
                   help="alpha 消耗函数: OF=O'Brien-Fleming, Pocock, WT=Wang-Tsiatis, "
                        "HSD=Hwang-Shih-DeCani(gamma, 经 --rho), KimDeMets(asOF)")
    # Adaptive
    p.add_argument("--n_stages_adapt", type=int, default=2)
    p.add_argument("--effect_adaptive", type=float, default=0.4)
    p.add_argument("--adaptive_type", type=str, default="SSR")
    # Survival Exact
    p.add_argument("--alpha_exact", type=float, default=0.05)
    p.add_argument("--power_exact", type=float, default=0.8)
    p.add_argument("--hr_exact", type=float, default=0.75)
    p.add_argument("--accrual_exact", type=float, default=12)
    p.add_argument("--followup_exact", type=float, default=12)
    p.add_argument("--dropout_exact", type=float, default=0.05)
    p.add_argument("--event_rate_exact", type=float, default=0.3)
    p.add_argument("--n_stages_exact", type=int, default=1)
    # ═══ NEW v3.5: PASS-survival extensions (7) ═══
    # Survival Equivalence (TOST on HR)
    p.add_argument("--eq_margin_surv", type=float, default=1.25)
    # Survival Superiority by a margin (HR)
    p.add_argument("--sup_margin_surv", type=float, default=0.8)
    p.add_argument("--sup_hr", type=float, default=0.67)
    # Cox covariate power (Vittinghoff)
    p.add_argument("--cox_hr", type=float, default=2.0)
    p.add_argument("--cox_r2", type=float, default=0.3)
    p.add_argument("--cox_prev", type=float, default=0.5)
    p.add_argument("--cox_event_prop", type=float, default=0.3)
    # One-sample exponential
    p.add_argument("--median0", type=float, default=12.0)
    p.add_argument("--median1", type=float, default=18.0)
    # Competing risks (cumulative incidence)
    p.add_argument("--ci_control", type=float, default=0.2)
    p.add_argument("--ci_treatment", type=float, default=0.1)
    # Recurrent events (Andersen-Gill)
    p.add_argument("--rate_control", type=float, default=1.0)
    p.add_argument("--rate_ratio", type=float, default=0.6)
    p.add_argument("--recur_followup", type=float, default=2.0)
    # Historical control log-rank
    p.add_argument("--new_median", type=float, default=18.0)
    p.add_argument("--hist_n", type=float, default=100.0)
    # ═══ NEW v3.6: PASS Group-Sequential extensions (rpact-backed) ═══
    # Two proportions (difference / ratio / odds-ratio)
    p.add_argument("--gs_proportion_metric", type=str, default="difference",
                   choices=["difference", "ratio", "or"],
                   help="gsd_proportion 的效应度量: difference(默认)/ratio/or")
    p.add_argument("--gs_ratio", type=float, default=0.8,
                   help="gsd_proportion ratio 模式: 治疗组比例 = 对照组 × ratio")
    p.add_argument("--gs_or", type=float, default=0.5,
                   help="gsd_proportion OR 模式: 治疗组比值比")
    # Two survival / hazard-rate (control median -> lambda2)
    p.add_argument("--gs_median_control", type=float, default=12.0,
                   help="gsd_survival/gsd_hazard 对照中位生存(月), 推导 lambda2")
    # Two Poisson rates
    p.add_argument("--gs_rate1", type=float, default=0.6,
                   help="gsd_poisson 治疗组发生率 (lambda1, /人年)")
    p.add_argument("--gs_rate2", type=float, default=1.0,
                   help="gsd_poisson 对照组发生率 (lambda2, /人年)")
    p.add_argument("--gs_poisson_time", type=float, default=2.0,
                   help="gsd_poisson 每人随访时间(年)")
    # ── Adaptive Monte-Carlo simulator (test=adaptive_simulate) ──
    # 纯 Python 蒙特卡洛自适应/成组序贯仿真器 (无 R, 无 shell, 直接运行)
    p.add_argument("--sim_design", type=str, default="group_sequential",
                   choices=["group_sequential", "adaptive_reestimate", "drop_the_loser"],
                   help="仿真设计类型 / simulation design")
    p.add_argument("--n_simulations", type=int, default=10000,
                   help="蒙特卡洛重复次数 / Monte-Carlo replications")
    p.add_argument("--sim_n", type=int, default=100,
                   help="每组样本量 (仿真用) / per-arm sample size for simulation")
    p.add_argument("--effect_size", type=float, default=0.3,
                   help="Cohen's d (仿真效应量)")
    p.add_argument("--effect_sizes", type=str, default=None,
                   help="drop_the_loser 各臂 d 逗号列表, 如 '0.2,0.35,0.5'")
    p.add_argument("--interim_looks", type=int, default=2,
                   help="分析次数 (含最终) / number of looks incl. final")
    p.add_argument("--spending_function", type=str, default="obrien_fleming",
                   choices=["obrien_fleming", "pocock", "power_family"],
                   help="alpha 消耗函数 / alpha spending function")
    p.add_argument("--rho", type=float, default=3.0,
                   help="HSD / Kim-DeMets 消耗函数的 gammaA (Hwang-Shih-DeCani γ, 默认 3.0)")
    p.add_argument("--wt_delta", type=float, default=0.25,
                   help="Wang-Tsiatis 参数 Δ (仅 --spending_func WT 生效, 默认 0.25)")
    p.add_argument("--futility", action="store_true", help="加入非绑定 futility 边界")
    p.add_argument("--beta", type=float, default=0.2, help="futility beta-spending")
    p.add_argument("--reestimate_method", type=str, default="promising_zone",
                   choices=["promising_zone"], help="样本量再估计方法")
    p.add_argument("--interim_fraction", type=float, default=0.5,
                   help="SSR/选臂 interim 信息比例")
    p.add_argument("--target_cp", type=float, default=0.9, help="SSR 目标条件功效")
    p.add_argument("--max_inflation", type=float, default=2.0, help="SSR 二阶段样本量上限倍数")
    p.add_argument("--n_arms", type=int, default=3, help="drop_the_loser 处理臂数")
    p.add_argument("--selection_fraction", type=float, default=0.5, help="选臂 interim 比例")
    p.add_argument("--correction", type=str, default="dunnett",
                   choices=["dunnett", "bonferroni"], help="多臂多重性校正")
    p.add_argument("--optimize", action="store_true",
                   help="网格搜索达到 --power 的最小每组样本量")
    p.add_argument("--n_min", type=int, default=10, help="--optimize 样本量下界")
    p.add_argument("--n_max", type=int, default=1000, help="--optimize 样本量上界")
    p.add_argument("--visualize", action="store_true", help="生成仿真结果 PNG")
    p.add_argument("--sim_output", type=str, default=None, help="仿真结果 JSON 输出路径")
    p.add_argument("--sim_seed", type=int, default=None, help="随机种子")
    # ── Curve mode (power / sample-size curves) ──
    p.add_argument("--n_seq", type=str, default=None,
                   help="样本量序列: 显式 '20,40,200' 或自动 '20:20:200'(起:步:止) → 绘制 power 曲线")
    p.add_argument("--power_seq", type=str, default=None,
                   help="效能序列: 显式 '0.6,0.7,0.95' 或自动 '0.6:0.05:0.95' → 绘制样本量曲线")
    p.add_argument("--plot_effects", type=str, default=None,
                   help="多效应量叠加(可选): '0.3,0.5,0.8' 画多条曲线做敏感性分析")
    p.add_argument("--effect_seq", type=str, default=None,
                   help="效应量连续序列: 显式 '0.1,0.2,0.9' 或自动 '0.1:0.05:0.9'(起:步:止) → "
                        "绘制效应量轴曲线(x=效应量; 配 --n_seq 时 y=效能, 配 --power_seq 时 y=所需样本量)")
    p.add_argument("--dist_plot", action="store_true", default=False,
                   help="① H0/H1 分布重叠图：标准化效应空间画两条正态密度并着色 α/β 区"
                        "(支持 ttest*/proportion*/survival)")
    p.add_argument("--power_time_seq", type=str, default=None,
                   help="③ 生存随访-效能曲线(仅 survival)：随访时长序列(单位与 event_rate 一致，如年 '1:0.5:4')"
                        "→ x=时长 y=效能；需配合 --event_rate / --accrual_time")
    p.add_argument("--heatmap", action="store_true", default=False,
                   help="④ 效能热力图：需 --n_seq(样本量) + --effect_seq(效应量) 两序列，"
                        "绘制效能填充热力图(支持 9 个曲线 test)")
    p.add_argument("--out", type=str, default=None,
                   help="曲线 PNG 输出路径 (默认系统临时目录)")

    # ── P1-C: 本地模拟验证闭环（verify.py 桥接，默认关闭）──
    # 把解析解（来自 pwr/coze 的 n 及组序贯边界）回代 Monte-Carlo，独立验证其
    # 真实 power / TIE。默认不触发；--verify 显式开启。模块纯本地、零联网。
    pv = p.add_argument_group("P1-C verification (本地模拟验证闭环)")
    pv.add_argument("--verify", action="store_true",
                    help="P1-C: 开启本地 Monte-Carlo 验证闭环（对 --verify-design 指定的设计，"
                         "用 --verify-n 回代模拟，校验 power ±2pp / TIE ±0.5pp）")
    pv.add_argument("--verify-design", default="ttest_ind",
                    choices=["ttest_ind", "ttest_one", "ttest_paired",
                             "proportion_two", "survival", "group_sequential",
                             "adaptive_reestimate"],
                    help="P1-C 验证对象设计类型（默认 ttest_ind）")
    pv.add_argument("--verify-n", type=int, default=None,
                    help="P1-C 回代的样本量 n（解析解给出的 n；必填，否则验证无意义）")
    pv.add_argument("--verify-power", type=float, default=0.8,
                    help="P1-C 名义功效目标（待验证）")
    pv.add_argument("--verify-nsim", type=int, default=20000,
                    help="P1-C Monte-Carlo 重复次数（上限 500000）")
    pv.add_argument("--verify-side", choices=["one", "two"], default="two")
    pv.add_argument("--verify-effect-size", type=float, default=None,
                    help="P1-C 连续端点 Cohen's d（ttest_*/group_sequential/adaptive）")
    pv.add_argument("--verify-p1", type=float, default=None, help="P1-C 治疗组比例")
    pv.add_argument("--verify-p2", type=float, default=None, help="P1-C 对照组比例")
    pv.add_argument("--verify-hr", type=float, default=None, help="P1-C 风险比 HR")
    pv.add_argument("--verify-median-control", type=float, default=None,
                    help="P1-C 对照中位生存（与 HR 同单位）")
    pv.add_argument("--verify-accrual", type=float, default=None, help="P1-C 入组期")
    pv.add_argument("--verify-followup", type=float, default=None, help="P1-C 末例随访期")
    pv.add_argument("--verify-boundaries", type=str, default=None,
                    help="P1-C 组序贯 z 边界（rpact/gsDesign 输出，逗号分隔）。"
                         "强烈建议提供——这才是独立验证；不提供则用内置 Lan-DeMets 自算（仅 sanity）")
    pv.add_argument("--verify-looks", type=int, default=2)
    pv.add_argument("--verify-spending", default="obrien_fleming",
                    choices=["obrien_fleming", "pocock"])
    pv.add_argument("--verify-expected-events", type=float, default=None,
                    help="P1-C 生存设计解析期望事件数（校验容差 ±5%%）")
    pv.add_argument("--verify-interim-fraction", type=float, default=None,
                    help="P1-C 适应性 SSR interim 信息比例")
    pv.add_argument("--verify-target-cp", type=float, default=None,
                    help="P1-C 适应性 SSR 目标条件功效")
    pv.add_argument("--verify-max-inflation", type=float, default=None,
                    help="P1-C 适应性 SSR 二阶段样本量上限倍数")
    pv.add_argument("--verify-json", default=None, help="P1-C 验证报告 JSON 输出路径")
    pv.add_argument("--verify-no-tie", action="store_true",
                    help="P1-C 跳过 H0 TIE 检验")

    # ── 出图模式（ct-base §19.9）──
    p.add_argument("--figure-mode", dest="figure_mode", choices=["svg_inline", "png_file"],
                   default=None,
                   help="图形呈现模式: svg_inline(默认,内联对话流) / png_file(本地 cairosvg 转 PNG)。"
                        "也可经环境变量 CTSS_FIGURE_MODE 设置。")

    return p


def main():
    p = build_parser()
    args = p.parse_args()

    # ── Security: validate every user string that reaches generated R code ──
    # These are interpolated into R string literals; enforce strict allowlists so
    # they can never inject arbitrary R code. Fail fast with a clear message.
    try:
        _validate_token("--adaptive_type", args.adaptive_type)
        _validate_token("--design", args.design)
        _validate_token("--spending_func", args.spending_func)
        _validate_token("--effect_name", args.effect_name)
        if args.test == "adaptive_simulate":
            _validate_token("--sim_design", args.sim_design)
            _validate_token("--spending_function", args.spending_function)
            _validate_token("--reestimate_method", args.reestimate_method)
            _validate_token("--correction", args.correction)
            if args.effect_sizes is not None:
                if not re.match(r'^[0-9.,\- ]+$', args.effect_sizes):
                    raise ValueError(
                        t("error.effect_sizes_invalid", value=args.effect_sizes))
            if args.sim_output is not None:
                _validate_path(args.sim_output)
        if args.out is not None:
            _validate_path(args.out)  # raises ValueError if unsafe
    except ValueError as e:
        p.error(str(e))

    # ═══ E1/E2: 自然语言确定性预路由（零 LLM，仅本地快速预解析）═══
    # 若提供 --nl，先用确定性规则识别 test + 提取参数，结果 write-thru 到 args 作为强信号；
    # 置信度低 / 参数不全时打印结构化提示（不静默错参、不阻断），剩余交由 coze LLM 补全。
    if args.nl:
        if not _NL_AVAILABLE:
            print("# [NL-route] 本地 NL 解析模块不可用，跳过 --nl 预路由，交由 coze LLM 解析")
        else:
            _nl = args.nl
            _cls = _nl_classify(_nl)
            if _cls.get("test"):
                args.test = _cls["test"]
                print("# [NL-route] test=%s (confidence=%s, matched=%s)"
                      % (args.test, _cls["confidence"], ",".join(_cls.get("matched", [])) or "-"))
                if _cls.get("needs_llm_fallback"):
                    print("# [NL-route] 终点类型置信度低，建议 coze LLM 兜底确认")
                for _m in _cls.get("missing", []):
                    print("# [NL-route] 缺关键信息: %s" % _m)
            else:
                print("# [NL-route] 未能从自然语言识别 test，交由 coze LLM 解析")
            # 参数提取：仅把 NL 中明确给出的参数 write-thru 到 args（不推断、不补默认）
            _pe = _nl_extract(_nl, test=args.test)
            for _k, _v in _pe.get("params", {}).items():
                if hasattr(args, _k):
                    setattr(args, _k, _v)
            if _pe.get("needs_llm_fallback"):
                _note = "; ".join(_pe.get("notes", [])) or "参数识别不全"
                print("# [NL-params] 部分参数需 coze LLM 兜底: " + _note)

    # SECURITY: dry-run is the SAFE DEFAULT. Execution requires an explicit
    # opt-in (--yes / -y) so generated R code is never run silently.
    confirmed = args.yes and not args.dry_run

    # ── Solve direction: --nobs given → solve for power; else solve for n ──
    if args.nobs is not None and args.nobs > 0:
        solve_for_power = True
    else:
        solve_for_power = False
        args.nobs = None

    # ── Numeric range validation ──
    _RANGE_RULES = {
        "alpha": (0, 0.5), "power": (0, 1),
        "auc0": (0, 1), "auc1": (0, 1),
        "correlation": (-1, 1), "icc": (0, 1),
        "margin": (0, None), "hazard_ratio": (0, None),
        "ni_margin_surv": (0, None), "sup_margin": (0, None),
        "delta_sup": (0, None),
        "ve_control": (0, 1), "ve_treatment": (0, 1),
        "prob_control": (0, 1), "prob_treatment": (0, 1),
        "p_control_sup": (0, 1), "p_control_current": (0, 1),
        "event_rate_exact": (0, 1), "dropout_exact": (0, 1),
        "p1": (0, 1), "p2": (0, 1),
        "eq_margin_surv": (0, None), "sup_margin_surv": (0, None), "sup_hr": (0, None),
        "cox_hr": (0, None), "cox_r2": (0, 1), "cox_prev": (0, 1),
        "cox_event_prop": (0, 1), "median0": (0, None), "median1": (0, None),
        "ci_control": (0, 1), "ci_treatment": (0, 1),
        "rate_control": (0, None), "rate_ratio": (0, None),
        "recur_followup": (0, None), "new_median": (0, None), "hist_n": (0, None),
        "gs_ratio": (0, 1), "gs_or": (0, None), "gs_median_control": (0, None),
        "gs_rate1": (0, None), "gs_rate2": (0, None), "gs_poisson_time": (0, None),
        "nobs": (0, None),
    }
    _range_errors = []
    for label, (lo, hi) in _RANGE_RULES.items():
        val = getattr(args, label, None)
        if val is None:
            continue
        if lo is not None and val <= lo:
            _range_errors.append(t("validation.range_error_gt", label=label, bound=lo, val=val))
        if hi is not None and val >= hi:
            _range_errors.append(t("validation.range_error_lt", label=label, bound=hi, val=val))
    if _range_errors:
        print(t("validation.failed"))
        for e in _range_errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    # ── 效应量 / 检验方向统一处理 (--side / --sd) ──
    # alt: one-sided -> "greater" (预期处理组更优); two-sided -> "two.sided"
    alt = "greater" if args.side == "one" else "two.sided"
    # d_val: 提供 --sd 时 --effect 视为原始均差 Δ, 自动折算 d = Δ/sd; 否则 --effect 直接为 d
    if args.sd is not None and args.sd > 0:
        d_val = (args.effect if args.effect is not None else 0.5) / args.sd
    else:
        d_val = args.effect if args.effect is not None else 0.5

    if not args.test:
        if args.nl:
            p.error(t("error.test_required")
                    + "（自然语言路由未能识别终点类型：请用 --test 显式指定，或换种表述后重试）")
        else:
            p.error(t("error.test_required"))

    # ── 假设清单显式化（ct-update 建议 ct-samplesize::E）──
    # 独立于后端（coze/R），仅做可审计性清单输出，不触碰数值真相源。
    if args.show_assumptions:
        try:
            import assumption_block as _ab
        except ImportError:
            import scripts.assumption_block as _ab  # 作为脚本子模块时
        block = _ab.build_assumption_block(args, args.test, p)
        print("=" * 60)
        print("假设清单 / Assumption Block")
        print("=" * 60)
        print(_ab.json.dumps(block, ensure_ascii=False, indent=2))
        sys.exit(0)

    # ═════════════════════════════════════════════════════════════════════════
    # 统一后端调度（coze 权威 / 本地 Python 兜底 / 本地 R 开发后端）
    # ═════════════════════════════════════════════════════════════════════════
    ctx = {
        "confirmed": confirmed,
        "solve_for_power": solve_for_power,
        "alt": alt,
        "d_val": d_val,
        "curve": bool(args.n_seq or args.power_seq or args.effect_seq
                     or args.dist_plot or args.power_time_seq or args.heatmap),
        "show_code": bool(args.show_code),
        "dry_run": bool(args.dry_run),
        # R 真相源开关：默认回传完整 R 源码 + R 数值（repro.r），对齐 meta-analysis 的
        # "每个分析默认回传可复现 R 代码" 行为（用户规则 2026-08-29：默认分析回传 R 代码）。
        # 旧逻辑仅在 --show-code / CTSS_RETURN_R_CODE 时开启，导致 coze 默认根本不被要求
        # 返回 R 代码、HTML 报告与对话都拿不到（即用户报的"默认不回传 R 代码"）。
        "return_r_code": True,
    }

    try:
        backend = select_backend(args.test)  # v5: 唯一后端 = coze（无本地回退）
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)

    # ── 待执行载荷预览（local-r → R 源码；coze → 请求信封；python → 无）──
    gated = backend.requires_confirmation          # 本地 R 需 --yes；coze / Python 不需要
    payload = backend.preview(args.test, args, ctx)
    if payload is not None and (args.show_code or args.dry_run or (gated and not confirmed)):
        _hdr = t("header.r_code") if gated else t("header.coze_request")
        print("=" * 60)
        print(_hdr)
        print("=" * 60)
        print(payload)
        print("=" * 60)

    if gated and not confirmed:
        print(t("safe_preview.not_executed_curve") if ctx["curve"]
              else t("safe_preview.not_executed"))
        return
    if args.dry_run:
        return

    if gated:
        print(t("exec.running"))
        sys.stdout.flush()

    try:
        res = backend.compute(args.test, args, ctx)
    except RuntimeError as exc:
        print(str(exc))
        sys.exit(1)

    if res.text:
        print(res.text)

    # ── 图形产物（coze 返回 SVG/HTML；本地 R 直接写 PNG）──
    render_figures(res.figures, args.test, figure_mode=args.figure_mode)
    # v5.3.2：聚合 HTML 报告（stats + 内联 SVG + R 复现脚本，单文件浏览器直接打开）
    try:
        from rendering import render_html_report  # type: ignore  # adapters/rendering.py

        _report_env = {
            "status": "ok",
            "stats": res.r_result or res.meta,
            "narrative": res.text,
            "figures": [
                {"format": f.format, "content": f.content, "caption": f.caption}
                for f in res.figures
            ],
            "repro": {"r": res.r_code} if res.r_code else None,
            "warnings": [],
            # 契约漂移标记（ct-base §20.9）：透传自 compute 的 meta，供渲染横幅消费
            "_needs_upgrade": bool(res.meta.get("_needs_upgrade", False)),
            "_contract_drift": res.meta.get("_contract_drift", []) or [],
        }
        _rp = render_html_report(_report_env, out_dir=_outputs_dir(),
                                 test=args.test, backend=res.backend or "coze")
        if _rp:
            print('__FIGURE__ html %s caption="ct-samplesize 结果报告"' % _rp)
    except Exception as _e:  # noqa: BLE001 - HTML 报告生成失败不阻断主流程
        print("# HTML 报告生成跳过: %s" % _e)
    # coze 端无图（svglite/cairo 缺失）但返回曲线数值 → 本地生成 SVG 兜底（ct-base §19）。
    # 仅在 coze 未返回任何图形时才兜底——否则同一曲线会被处理两遍（coze SVG + 本地
    # fallback 两份输出），且持久化文件可能被无参考线的 fallback 版覆盖（2026-08-20 修复）。
    if not res.figures:
        render_curve_fallback(res.meta, args.test,
                              target_power=getattr(args, "power", None) or 0.8,
                              ref_n=getattr(args, "nobs", None))

    # ── 自动附带曲线（v5.3.2 起每种检验的默认出图由契约 default_curve 分别配置）──
    # 规则: forward（求 n）→ 自动补「样本量随把握度」曲线；reverse（求 power）→
    # 自动补「把握度随样本量」曲线。仅当：① 该 test 契约 default_curve=true；② 用户未
    # 显式指定曲线（--n_seq / --power_seq）；③ 非 dry-run；④ coze 路径（非本地 R）。
    # 关闭/开启方式：编辑 tests/coze_cases/_contract_index.json 的 default_curve 字段，
    # 或显式指定 --n_seq / --power_seq（走用户自己的曲线）、--dry-run 关闭。
    if (not ctx["curve"] and args.test in _auto_curve_tests()
            and not args.dry_run and not gated):
        try:
            args2 = argparse.Namespace(**vars(args))
            args2.n_seq = None
            args2.power_seq = None
            args2.plot_effects = None
            ctx2 = dict(ctx)
            ctx2["curve"] = True
            _what = ""
            if solve_for_power and args.nobs:
                _n = args.nobs
                _n_min = max(5, int(_n * 0.5))
                _n_max = max(_n_min + 8, int(_n * 1.5))
                _step = max(1, round((_n_max - _n_min) / 8))
                args2.n_seq = "%d:%d:%d" % (_n_min, _step, _n_max)
                _what = "把握度随样本量（以 n=%d 为中心 ±50%%）" % _n
            else:
                args2.power_seq = "0.6:0.05:0.95"
                _what = "样本量随把握度（power 0.60~0.95）"
            res2 = backend.compute(args.test, args2, ctx2)
            if res2 and getattr(res2, "figures", None):
                render_figures(res2.figures, args.test, figure_mode=args.figure_mode)
            else:
                # coze 无图 → 本地兜底（★ 参考线目标 = 用户 --power 或默认 0.8）
                render_curve_fallback(getattr(res2, "meta", None), args.test,
                                      target_power=getattr(args2, "power", None) or 0.8,
                                      ref_n=getattr(args2, "nobs", None))
            print("# 已自动附带%s曲线（简单单/两组问题默认出图；如需关闭请显式指定 "
                  "--n_seq / --power_seq 或 --dry-run）" % _what)
        except Exception as _e:  # noqa: BLE001 - 自动曲线失败不阻断主结果
            print("# 自动曲线生成跳过: %s" % _e)

    # ── 默认图形层（v5.6 起全部上 coze）────────────────────────────────────
    # 架构：coze 端 R（coze_figure_layer.R）为主出图；若其失败，coze 内部回退到
    #   figure_kit.py（随包上传到 coze 的 Python 兜底，位于 adapters/coze/scripts/）。
    #   本地是「瘦客户端」：只承接 coze 回传的 `figures` 数组，交由上方 render_figures
    #   统一落盘 / 内联 / 聚合进 HTML 报告，本地绝不再渲染（详见 SKILL.md v5.6 说明）。
    #   （历史上此处有一段本地透出循环，与 render_figures 重复，已在 v5.6 删除。）

    # coze 返回未填充 meta 时（无 __CTSS_RESULT__ 标记）res.meta 可为 None，防御性取空字典
    _png = (res.meta or {}).get("png_path")
    if _png:
        print(t("info.png_saved", path=_png))

    # ── R 源码 / R 数值（默认回传并展示，对齐 meta-analysis；2026-08-29 修订）──
    # 旧逻辑仅在 --show-code / CTSS_RETURN_R_CODE 时展示；现默认展示（coze 始终回传 repro.r）。
    if res.r_code and not gated:
        print("=" * 60)
        print(t("header.r_code"))
        print("=" * 60)
        print(res.r_code)
    if res.r_result and not gated:
        print("-" * 60)
        print(json.dumps(res.r_result, ensure_ascii=False, indent=2))
    print("=" * 60)

    # ── P1-C: 本地模拟验证闭环（独立 Monte-Carlo，默认关闭）──
    if args.verify:
        if _verify_run is None:
            print("# [verify] 模块 verify.py 不可用，跳过验证。")
        elif not args.verify_n:
            print("# [verify] 未提供 --verify-n（解析解给出的样本量）；无 n 则验证无意义，跳过。")
        else:
            try:
                bnds = None
                if args.verify_boundaries:
                    bnds = [float(x) for x in
                            args.verify_boundaries.replace(" ", "").split(",") if x]
                vparams = {k: v for k, v in {
                    "effect_size": args.verify_effect_size, "p1": args.verify_p1,
                    "p2": args.verify_p2, "hazard_ratio": args.verify_hr,
                    "median_control": args.verify_median_control,
                    "accrual": args.verify_accrual, "followup": args.verify_followup,
                    "interim_fraction": args.verify_interim_fraction,
                    "target_cp": args.verify_target_cp,
                    "max_inflation": args.verify_max_inflation,
                }.items() if v is not None}
                vrep = _verify_run(
                    args.verify_design, args.verify_n, alpha=args.alpha,
                    power=args.verify_power, side=args.verify_side,
                    nsim=args.verify_nsim, params=vparams, boundaries=bnds,
                    looks=(len(bnds) if bnds else args.verify_looks),
                    spending=args.verify_spending,
                    expected_events=args.verify_expected_events,
                    check_tie=not args.verify_no_tie)
                print(vrep if isinstance(vrep, str) else _verify_fmt(vrep))
                if args.verify_json:
                    with open(args.verify_json, "w", encoding="utf-8") as _vf:
                        json.dump(vrep, _vf, ensure_ascii=False, indent=2)
                    print("\n[verify] JSON -> %s" % args.verify_json)
            except SystemExit as _se:
                print("# [verify] 中止: %s" % _se)
            except Exception as _e:  # noqa: BLE001 - 验证失败不阻断主样本量结果
                print("# [verify] 验证失败（不影响主结果）: %s" % _e)


if __name__ == "__main__":
    main()
