#!/usr/bin/env python3
"""Build the polished submission performance report PDF from raw result JSONs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
TEAL = colors.HexColor("#008C95")
GREEN = colors.HexColor("#2E8B57")
AMBER = colors.HexColor("#D98700")
RED = colors.HexColor("#B64040")
INK = colors.HexColor("#243447")
MUTED = colors.HexColor("#607286")
PALE_BLUE = colors.HexColor("#EAF2F8")
PALE_TEAL = colors.HexColor("#E8F5F4")
PALE_AMBER = colors.HexColor("#FFF4DD")
LIGHT_LINE = colors.HexColor("#CCD6E0")


def load_json(relative: str) -> dict[str, Any]:
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def lower_is_better(base: float, candidate: float) -> float:
    return 100.0 * (base - candidate) / base


def higher_is_better(base: float, candidate: float) -> float:
    return 100.0 * (candidate - base) / base


def performance_gains(
    base: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, float]:
    return {
        "ttft": lower_is_better(base["mean_ttft_ms"], candidate["mean_ttft_ms"]),
        "ttfp": lower_is_better(
            base["mean_audio_ttfp_ms"], candidate["mean_audio_ttfp_ms"]
        ),
        "rtf": lower_is_better(base["mean_audio_rtf"], candidate["mean_audio_rtf"]),
        "e2e": lower_is_better(base["mean_e2el_ms"], candidate["mean_e2el_ms"]),
        "throughput": higher_is_better(
            base["request_throughput"], candidate["request_throughput"]
        ),
    }


def register_fonts(font_dir: Path) -> tuple[str, str]:
    body_candidates = [
        font_dir / "Deng.ttf",
        font_dir / "NotoSansSC-VF.ttf",
        font_dir / "simhei.ttf",
    ]
    bold_candidates = [
        font_dir / "Dengb.ttf",
        font_dir / "Noto Sans SC Bold (TrueType).otf",
        font_dir / "simhei.ttf",
    ]
    body_path = next((path for path in body_candidates if path.is_file()), None)
    bold_path = next((path for path in bold_candidates if path.is_file()), None)
    if body_path is None or bold_path is None:
        raise FileNotFoundError(
            f"Chinese font not found under {font_dir}; tried {body_candidates + bold_candidates}"
        )
    pdfmetrics.registerFont(TTFont("ReportBody", str(body_path)))
    pdfmetrics.registerFont(TTFont("ReportBold", str(bold_path)))
    return "ReportBody", "ReportBold"


def paragraph_styles(body_font: str, bold_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleCN",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=24,
            leading=34,
            textColor=NAVY,
            alignment=TA_LEFT,
            wordWrap="CJK",
            spaceAfter=5 * mm,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCN",
            parent=base["Normal"],
            fontName=body_font,
            fontSize=11,
            leading=17,
            textColor=MUTED,
            wordWrap="CJK",
            spaceAfter=4 * mm,
        ),
        "h1": ParagraphStyle(
            "H1CN",
            parent=base["Heading1"],
            fontName=bold_font,
            fontSize=16,
            leading=22,
            textColor=NAVY,
            wordWrap="CJK",
            spaceBefore=2 * mm,
            spaceAfter=3 * mm,
        ),
        "h2": ParagraphStyle(
            "H2CN",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=11.5,
            leading=17,
            textColor=BLUE,
            wordWrap="CJK",
            spaceBefore=2 * mm,
            spaceAfter=2 * mm,
        ),
        "body": ParagraphStyle(
            "BodyCN",
            parent=base["BodyText"],
            fontName=body_font,
            fontSize=9.2,
            leading=14.5,
            textColor=INK,
            wordWrap="CJK",
            spaceAfter=2.2 * mm,
        ),
        "small": ParagraphStyle(
            "SmallCN",
            parent=base["BodyText"],
            fontName=body_font,
            fontSize=7.5,
            leading=11,
            textColor=MUTED,
            wordWrap="CJK",
        ),
        "callout": ParagraphStyle(
            "CalloutCN",
            parent=base["BodyText"],
            fontName=bold_font,
            fontSize=11,
            leading=17,
            textColor=NAVY,
            wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "TableCN",
            parent=base["BodyText"],
            fontName=body_font,
            fontSize=7.3,
            leading=10,
            textColor=INK,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
        "table_bold": ParagraphStyle(
            "TableBoldCN",
            parent=base["BodyText"],
            fontName=bold_font,
            fontSize=7.4,
            leading=10,
            textColor=colors.white,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "CodeCN",
            parent=base["Code"],
            fontName="Courier",
            fontSize=6.9,
            leading=10.5,
            textColor=INK,
            backColor=colors.HexColor("#F4F6F8"),
            borderColor=LIGHT_LINE,
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=3 * mm,
        ),
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def styled_table(
    rows: list[list[Any]],
    widths: list[float],
    body_font: str,
    header_rows: int = 1,
    alignments: dict[int, str] | None = None,
) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=header_rows, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), colors.white),
        ("FONTNAME", (0, 0), (-1, header_rows - 1), "ReportBold"),
        ("FONTNAME", (0, header_rows), (-1, -1), body_font),
        ("FONTSIZE", (0, 0), (-1, -1), 7.3),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.35, LIGHT_LINE),
    ]
    for row in range(header_rows, len(rows)):
        if (row - header_rows) % 2 == 1:
            commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F6F8FA")))
    if alignments:
        for column, alignment in alignments.items():
            commands.append(("ALIGN", (column, header_rows), (column, -1), alignment))
    table.setStyle(TableStyle(commands))
    return table


def kpi_cards(items: list[tuple[str, str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    cells = []
    for label, value, note in items:
        cells.append(
            p(
                f'<font color="#607286" size="7">{label}</font><br/>'
                f'<font color="#17365D" size="15"><b>{value}</b></font><br/>'
                f'<font color="#2E8B57" size="7">{note}</font>',
                styles["body"],
            )
        )
    table = Table([cells], colWidths=[34.5 * mm] * len(cells), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.7, LIGHT_LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LIGHT_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def gain_chart(values: list[tuple[str, float]], font_name: str) -> Drawing:
    width = 172 * mm
    height = 52 * mm
    drawing = Drawing(width, height)
    x0 = 38 * mm
    usable = 124 * mm
    max_value = 7.0
    colors_for_bars = [BLUE, TEAL, GREEN, BLUE, TEAL]
    for index, ((label, value), fill) in enumerate(zip(values, colors_for_bars)):
        y = height - (index + 1) * 9.5 * mm
        drawing.add(String(0, y + 1.5 * mm, label, fontName=font_name, fontSize=7.4, fillColor=INK))
        drawing.add(Rect(x0, y, usable, 4.7 * mm, fillColor=colors.HexColor("#E8EDF2"), strokeColor=None))
        drawing.add(
            Rect(
                x0,
                y,
                usable * min(value, max_value) / max_value,
                4.7 * mm,
                fillColor=fill,
                strokeColor=None,
            )
        )
        drawing.add(
            String(
                x0 + usable + 2 * mm,
                y + 1.2 * mm,
                f"{value:.2f}%",
                fontName=font_name,
                fontSize=7.4,
                fillColor=NAVY,
            )
        )
    return drawing


def page_decor(canvas: Any, doc: Any) -> None:
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setFont("ReportBody", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, A4[1] - 10 * mm, "MiniCPM-o 4.5 昇腾 vLLM-Omni 推理优化")
        canvas.setStrokeColor(LIGHT_LINE)
        canvas.line(18 * mm, A4[1] - 12 * mm, A4[0] - 18 * mm, A4[1] - 12 * mm)
    canvas.setStrokeColor(LIGHT_LINE)
    canvas.line(18 * mm, 12 * mm, A4[0] - 18 * mm, 12 * mm)
    canvas.setFont("ReportBody", 7.2)
    canvas.setFillColor(MUTED)
    footer_date = getattr(doc, "report_date", "")
    canvas.drawString(
        18 * mm,
        7.5 * mm,
        f"HiDevLab 910C 分配 | vLLM-Omni 0.25.0+npu | {footer_date}",
    )
    canvas.drawRightString(A4[0] - 18 * mm, 7.5 * mm, f"第 {page} 页")
    canvas.restoreState()


def build_report(output: Path, font_dir: Path) -> None:
    body_font, bold_font = register_fonts(font_dir)
    styles = paragraph_styles(body_font, bold_font)

    baseline = load_json("results/performance/baseline_repeat_full_c1_n32.json")
    codec20 = load_json("results/performance/codec20_full_c1_n32.json")
    run1 = load_json("results/performance/steps9_full_c1_n32.json")
    run2 = load_json("results/performance/steps9_repeat_c1_n32.json")
    matrix4 = load_json("results/performance/steps9_matrix_c4_n64.json")
    matrix8 = load_json("results/performance/steps9_matrix_c8_n128.json")
    wer = load_json("results/accuracy/whisper_ab_c1_n32.json")
    asv = load_json("results/accuracy/asv_ab_c1_n32_strict.json")
    framework_commit = (
        ROOT / "evidence/environment/vllm-omni-commit.txt"
    ).read_text(encoding="utf-8").strip()
    captured_at = (
        ROOT / "evidence/environment/timestamp.txt"
    ).read_text(encoding="utf-8").strip()
    run1_gain = performance_gains(baseline, run1)
    run2_gain = performance_gains(baseline, run2)
    codec20_gain = performance_gains(baseline, codec20)
    wer_summary = wer["summary"]
    asv_summary = asv["summary"]
    asv_stats = asv_summary["paired_statistics"]
    asv_ci = asv_stats["mean_delta_ci95"]
    matrix_total = sum(
        int(result["completed"]) for result in (run2, matrix4, matrix8)
    )
    matrix_failed = sum(int(result["failed"]) for result in (run2, matrix4, matrix8))

    output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=17 * mm,
        title="MiniCPM-o 4.5 昇腾 vLLM-Omni 推理优化报告",
        author="MiniCPM-o 4.5 Ascend Optimization Team",
        subject="Ascend 910C inference optimization evidence report",
    )
    doc.report_date = captured_at[:10]

    story: list[Any] = []
    story.append(Spacer(1, 13 * mm))
    story.append(p("MiniCPM-o 4.5", styles["title"]))
    story.append(p("昇腾 vLLM-Omni 高性能推理优化报告", styles["title"]))
    story.append(
        p(
            "HiDevLab 单卡 910C 分配 · 流式语音生成 · 单变量 A/B · 三档并发矩阵",
            styles["subtitle"],
        )
    )
    story.append(Spacer(1, 3 * mm))
    cover_info = [
        ["子赛道", "vLLM-Omni 推理优化", "模型", "MiniCPM-o 4.5"],
        ["运行环境", "910C 分配；npu-smi=Ascend910", "框架提交", f"{framework_commit[:12]}..."],
        ["候选配置", "Token2Wav steps: 10 -> 9", "回退配置", "官方 challenge 基线副本"],
    ]
    info_table = Table(cover_info, colWidths=[23 * mm, 61 * mm, 24 * mm, 66 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                ("BACKGROUND", (2, 0), (2, -1), PALE_BLUE),
                ("FONTNAME", (0, 0), (-1, -1), body_font),
                ("FONTNAME", (0, 0), (0, -1), bold_font),
                ("FONTNAME", (2, 0), (2, -1), bold_font),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("GRID", (0, 0), (-1, -1), 0.45, LIGHT_LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 9 * mm))
    callout = Table(
        [
            [
                p(
                    f"核心结论：在相同 c1/n32 输入和计时口径下，两次 steps=9 "
                    f"候选复测的 Mean RTF 降低 {run1_gain['rtf']:.2f}%-"
                    f"{run2_gain['rtf']:.2f}%，Mean TTFP 降低 {run1_gain['ttfp']:.2f}%-"
                    f"{run2_gain['ttfp']:.2f}%，E2E 降低 {run1_gain['e2e']:.2f}%-"
                    f"{run2_gain['e2e']:.2f}%，吞吐提升 {run1_gain['throughput']:.2f}%-"
                    f"{run2_gain['throughput']:.2f}%；"
                    f"{wer_summary['evaluated_pairs']} 条代理 WER 与基线完全一致。",
                    styles["callout"],
                )
            ]
        ],
        colWidths=[174 * mm],
    )
    callout.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 1.0, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(callout)
    story.append(Spacer(1, 8 * mm))
    story.append(
        kpi_cards(
            [
                ("TTFT 降幅", f"{run1_gain['ttft']:.2f}-{run2_gain['ttft']:.2f}%", "两次候选复测"),
                ("TTFP 降幅", f"{run1_gain['ttfp']:.2f}-{run2_gain['ttfp']:.2f}%", "两次候选复测"),
                ("RTF 降幅", f"{run1_gain['rtf']:.2f}-{run2_gain['rtf']:.2f}%", "核心指标"),
                ("E2E 降幅", f"{run1_gain['e2e']:.2f}-{run2_gain['e2e']:.2f}%", "整体耗时"),
                ("吞吐增幅", f"{run1_gain['throughput']:.2f}-{run2_gain['throughput']:.2f}%", "req/s"),
            ],
            styles,
        )
    )
    story.append(Spacer(1, 9 * mm))
    story.append(
        p(
            "证据边界：性能 JSON 与环境快照来自报告运行；npu-smi 只显示通用设备名 "
            "Ascend910，不能独立认证具体子型号。WER/ASV 均为非官方配对代理，主办方"
            "正式精度评测前不宣称官方精度通过。",
            styles["small"],
        )
    )
    story.append(PageBreak())

    story.append(p("1. 优化方法与同机 A/B", styles["h1"]))
    story.append(
        p(
            "保留可读官方 challenge 配置作为基线，仅在 connector extra 中增加 "
            "<b>token2wav_n_timesteps: 9</b>，其默认值为 10。减少一次 flow-matching "
            "迭代会改变声学生成数值路径，因此必须同时检查性能、WER 和说话人相似度。",
            styles["body"],
        )
    )
    story.append(p("本次同机 A/B 口径", styles["h2"]))
    story.append(
        p(
            "同一份 HiDevLab 910C 分配、完整 Seed-TTS English、seed=0 shuffle、"
            "并发 1、2 个完整语音 warmup 和 32 个计时请求。基线与两次候选均为 "
            f"{baseline['completed']}/{baseline['num_prompts']}、"
            f"{run1['completed']}/{run1['num_prompts']}、"
            f"{run2['completed']}/{run2['num_prompts']} 成功，失败数均为 0。",
            styles["body"],
        )
    )
    story.append(
        p(
            "本地定义：TTFT 为请求到首个有效文本 token；TTFP 为请求到首个音频包；"
            "RTF 为音频生成计算耗时除以音频时长；E2E 为请求到完整响应结束；吞吐为"
            "完成请求数除以矩阵墙钟时间（req/s）。官方起止点以主办方脚本为准。",
            styles["small"],
        )
    )

    ab_rows = [
        ["指标", "基线 steps=10", "steps=9 run 1", "变化", "steps=9 run 2", "变化"],
        ["Mean TTFT", f"{baseline['mean_ttft_ms']:.3f} ms", f"{run1['mean_ttft_ms']:.3f} ms", f"-{run1_gain['ttft']:.2f}%", f"{run2['mean_ttft_ms']:.3f} ms", f"-{run2_gain['ttft']:.2f}%"],
        ["Mean TTFP", f"{baseline['mean_audio_ttfp_ms']:.3f} ms", f"{run1['mean_audio_ttfp_ms']:.3f} ms", f"-{run1_gain['ttfp']:.2f}%", f"{run2['mean_audio_ttfp_ms']:.3f} ms", f"-{run2_gain['ttfp']:.2f}%"],
        ["Mean RTF", f"{baseline['mean_audio_rtf']:.6f}", f"{run1['mean_audio_rtf']:.6f}", f"-{run1_gain['rtf']:.2f}%", f"{run2['mean_audio_rtf']:.6f}", f"-{run2_gain['rtf']:.2f}%"],
        ["Mean E2E", f"{baseline['mean_e2el_ms']:.3f} ms", f"{run1['mean_e2el_ms']:.3f} ms", f"-{run1_gain['e2e']:.2f}%", f"{run2['mean_e2el_ms']:.3f} ms", f"-{run2_gain['e2e']:.2f}%"],
        ["吞吐 (req/s)", f"{baseline['request_throughput']:.6f}", f"{run1['request_throughput']:.6f}", f"+{run1_gain['throughput']:.2f}%", f"{run2['request_throughput']:.6f}", f"+{run2_gain['throughput']:.2f}%"],
    ]
    story.append(
        styled_table(
            ab_rows,
            [27 * mm, 31 * mm, 31 * mm, 25 * mm, 31 * mm, 25 * mm],
            body_font,
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(p("steps=9 第二次复测相对同机基线的改善", styles["h2"]))
    story.append(
        gain_chart(
            [
                ("TTFT", run2_gain["ttft"]),
                ("TTFP", run2_gain["ttfp"]),
                ("RTF", run2_gain["rtf"]),
                ("E2E", run2_gain["e2e"]),
                ("吞吐", run2_gain["throughput"]),
            ],
            body_font,
        )
    )
    story.append(
        p(
            "两次候选复测之间，TTFT、TTFP、RTF、E2E 和吞吐的相对差异均小于 "
            "1%，说明候选方向一致。基线只运行一次，因此不能估计基线波动或宣称统计"
            "显著。这里的收益只针对相同输入、配置与计时口径，不与冷启动或 4 请求 "
            "smoke 混用。",
            styles["body"],
        )
    )
    story.append(PageBreak())

    story.append(p("2. 三档请求矩阵、尾延迟与高并发权衡", styles["h1"]))
    story.append(
        p(
            "本地 harness 进一步跑完与赛事配置对齐请求数、并发数和主要参数的 "
            "c1/n32、c4/n64、c8/n128 矩阵。"
            f"三档共 {matrix_total} 个计时请求全部成功、{matrix_failed} 失败；这只"
            "说明请求级完成，不等同主办方正式 pytest harness 或尾延迟稳定。",
            styles["body"],
        )
    )
    matrix_rows = [
        ["档位", "成功/失败", "TTFT", "TTFP", "RTF", "E2E", "吞吐 req/s"],
        ["c1/n32", f"{run2['completed']}/{run2['failed']}", f"{run2['mean_ttft_ms']:.3f} ms", f"{run2['mean_audio_ttfp_ms']:.3f} ms", f"{run2['mean_audio_rtf']:.6f}", f"{run2['mean_e2el_ms']:.3f} ms", f"{run2['request_throughput']:.6f}"],
        ["c4/n64", f"{matrix4['completed']}/{matrix4['failed']}", f"{matrix4['mean_ttft_ms']:.3f} ms", f"{matrix4['mean_audio_ttfp_ms']:.3f} ms", f"{matrix4['mean_audio_rtf']:.6f}", f"{matrix4['mean_e2el_ms']:.3f} ms", f"{matrix4['request_throughput']:.6f}"],
        ["c8/n128", f"{matrix8['completed']}/{matrix8['failed']}", f"{matrix8['mean_ttft_ms']:.3f} ms", f"{matrix8['mean_audio_ttfp_ms']:.3f} ms", f"{matrix8['mean_audio_rtf']:.6f}", f"{matrix8['mean_e2el_ms']:.3f} ms", f"{matrix8['request_throughput']:.6f}"],
    ]
    story.append(
        styled_table(
            matrix_rows,
            [18 * mm, 22 * mm, 26 * mm, 28 * mm, 24 * mm, 29 * mm, 25 * mm],
            body_font,
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(p("Median / p99 尾延迟", styles["h2"]))
    tail_rows = [
        ["档位", "Med TTFP", "p99 TTFP", "Med RTF", "p99 RTF", "Med E2E", "p99 E2E"],
        ["c1/n32", f"{run2['median_audio_ttfp_ms'] / 1000:.3f}s", f"{run2['p99_audio_ttfp_ms'] / 1000:.3f}s", f"{run2['median_audio_rtf']:.3f}", f"{run2['p99_audio_rtf']:.3f}", f"{run2['median_e2el_ms'] / 1000:.3f}s", f"{run2['p99_e2el_ms'] / 1000:.3f}s"],
        ["c4/n64", f"{matrix4['median_audio_ttfp_ms'] / 1000:.3f}s", f"{matrix4['p99_audio_ttfp_ms'] / 1000:.3f}s", f"{matrix4['median_audio_rtf']:.3f}", f"{matrix4['p99_audio_rtf']:.3f}", f"{matrix4['median_e2el_ms'] / 1000:.3f}s", f"{matrix4['p99_e2el_ms'] / 1000:.3f}s"],
        ["c8/n128", f"{matrix8['median_audio_ttfp_ms'] / 1000:.3f}s", f"{matrix8['p99_audio_ttfp_ms'] / 1000:.3f}s", f"{matrix8['median_audio_rtf']:.3f}", f"{matrix8['p99_audio_rtf']:.3f}", f"{matrix8['median_e2el_ms'] / 1000:.3f}s", f"{matrix8['p99_e2el_ms'] / 1000:.3f}s"],
    ]
    story.append(
        styled_table(
            tail_rows,
            [20 * mm, 25 * mm, 25 * mm, 24 * mm, 24 * mm, 27 * mm, 27 * mm],
            body_font,
        )
    )
    story.append(
        p(
            "c4/n64 的 p99 TTFP/E2E 达到 21.346s/22.967s，c8/n128 达到 "
            "14.036s/21.174s。成功率不能掩盖这一长尾；不同样本量下也不应把 c4 与 "
            "c8 的 p99 大小直接解释为并发越高反而越稳定。",
            styles["small"],
        )
    )
    story.append(Spacer(1, 3 * mm))
    ref_rows = [
        ["档位", "TTFT vs ref", "TTFP vs ref", "RTF vs ref", "E2E vs ref", "吞吐 vs ref"],
        ["c1/n32", "-5.99%", "-2.04%", "-0.31%", "+1.17%", "-1.16%"],
        ["c4/n64", "-7.46%", "-3.86%", "-9.28%", "-8.58%", "+8.33%"],
        ["c8/n128", "+0.69%", "+8.76%", "-8.12%", "-8.01%", "+8.71%"],
    ]
    story.append(p("相对赛事配置内参考值的定位", styles["h2"]))
    story.append(
        styled_table(
            ref_rows,
            [20 * mm, 29 * mm, 29 * mm, 29 * mm, 29 * mm, 31 * mm],
            body_font,
        )
    )
    story.append(
        p(
            "负数表示时延或 RTF 更低，吞吐列正数表示更高。官方参考值不是本机同次"
            "运行，因此只用于矩阵级定位，不能替代第 1 节同机 A/B。c8/n128 的 "
            "TTFP 高 8.76%，说明高并发存在首包与总体吞吐的明确权衡。",
            styles["small"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    reject_box = Table(
        [
            [
                p(
                    f"已淘汰方案：codec_chunk_frames 25 -> 20。虽然 TTFP 改善 "
                    f"{codec20_gain['ttfp']:.2f}%，但 RTF 恶化 {-codec20_gain['rtf']:.2f}%、"
                    f"E2E 恶化 {-codec20_gain['e2e']:.2f}%、吞吐下降 "
                    f"{-codec20_gain['throughput']:.2f}%，不作为"
                    "最终默认配置。",
                    styles["body"],
                )
            ]
        ],
        colWidths=[172 * mm],
    )
    reject_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_AMBER),
                ("BOX", (0, 0), (-1, -1), 0.8, AMBER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(reject_box)
    story.append(Spacer(1, 4 * mm))
    story.append(
        p(
            "尚未覆盖：官方 single-chunk latency 分布、NPU/AICore/HBM 利用率采样、"
            "长时间稳定性和多 session 调度。当前 JSON 不能支持这些结论。",
            styles["small"],
        )
    )
    story.append(PageBreak())

    story.append(p("3. 质量代理与精度边界", styles["h1"]))
    story.append(
        p(
            "steps=9 少一次声学迭代，不能只看速度。对与性能测试相同的 32 条 Seed-TTS "
            "English 样本分别保存基线和候选完整 WAV，再执行配对 WER 与说话人相似度检查。",
            styles["body"],
        )
    )
    quality_rows = [
        ["检查", "基线", "steps=9", "结果"],
        ["Whisper large-v3 proxy Mean WER", f"{100 * wer_summary['baseline_mean_wer']:.6f}%", f"{100 * wer_summary['candidate_mean_wer']:.6f}%", f"{wer_summary['evaluated_pairs']} 条归一化 WER 全部一致"],
        ["未校准 ASV proxy Mean SIM", f"{asv_summary['baseline_mean_similarity']:.8f}", f"{asv_summary['candidate_mean_similarity']:.8f}", f"{asv_summary['candidate_better_pairs']} 对提高，{asv_summary['candidate_worse_pairs']} 对降低"],
        ["ASV paired delta", "-", f"{asv_summary['candidate_minus_baseline_similarity']:.8f}", f"95% CI [{asv_ci['lower']:.5f}, {asv_ci['upper']:.5f}]"],
    ]
    story.append(
        styled_table(
            quality_rows,
            [49 * mm, 31 * mm, 31 * mm, 61 * mm],
            body_font,
            alignments={3: "LEFT"},
        )
    )
    story.append(Spacer(1, 5 * mm))
    story.append(p("ASV 配对统计", styles["h2"]))
    story.append(
        p(
            f"paired t-test p={asv_stats['paired_t_test']['pvalue']:.3f}，"
            f"Wilcoxon p={asv_stats['wilcoxon_signed_rank_test']['pvalue']:.3f}。"
            f"在这一未校准 CPU proxy 上，{asv_summary['evaluated_pairs']} 对的配对差异"
            "没有统计显著性；这不等于证明两个配置等价，也不构成 ASV 精度门禁。"
            "严格 v2 脚本将 checkpoint、"
            "源码、meta、seed/范围及 96 个输入 WAV 哈希绑定到运行指纹，并能拒绝旧"
            "进度文件。严格原始 JSON 已随包保存；validator 会核对固定指纹、源码与"
            "输入哈希、32/32 完成状态和代理计算质量门。",
            styles["body"],
        )
    )
    boundary_box = Table(
        [
            [
                p(
                    "重要边界：WER 使用相同 large-v3 checkpoint 的 OpenAI Whisper 实现；"
                    "ASV 使用相同 WavLM/ECAPA 代码和权重的 CPU 最小移植。两项结果均"
                    "标记 official_protocol=false，不能替代主办方正式 WER/ASV，也不能"
                    "将 CPU proxy 的绝对 SIM 与官方 ASV 门槛直接比较。",
                    styles["body"],
                )
            ]
        ],
        colWidths=[172 * mm],
    )
    boundary_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FCECEC")),
                ("BOX", (0, 0), (-1, -1), 0.8, RED),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(boundary_box)
    story.append(Spacer(1, 6 * mm))
    story.append(p("结果可审计性", styles["h2"]))
    audit_rows = [
        ["项目", "状态"],
        ["原始性能 JSON", "已保存，全部 completed == num_prompts 且 failed == 0"],
        ["提交文件 SHA-256", "RESULT_MANIFEST.sha256 + validate_submission.py 自动核验"],
        ["配置变化", "仅 token2wav_n_timesteps: 9，一键回退基线"],
        ["严格 ASV v2 JSON", "已随包保存；绑定固定指纹、96 个输入与 3 份源码哈希"],
        ["环境快照", "已保存 npu-smi、CANN/torch_npu/vLLM 版本、commit 与 pip-freeze"],
        ["共享资源", "/workspace/shared_assets 只读，未修改模型或数据集"],
    ]
    story.append(styled_table(audit_rows, [48 * mm, 124 * mm], body_font, alignments={1: "LEFT"}))
    story.append(PageBreak())

    story.append(p("4. 复现、提交与最终决定", styles["h1"]))
    story.append(p("候选服务启动", styles["h2"]))
    story.append(
        p(
            "cd /workspace/user_data/minicpm-vllm-omni/submission<br/>"
            "bash scripts/collect_env.sh<br/>"
            "CONFIG=\"$PWD/configs/experiment_steps9.yaml\" bash scripts/start_server.sh",
            styles["code"],
        )
    )
    story.append(p("第二终端执行 Demo、矩阵和自检", styles["h2"]))
    story.append(
        p(
            "cd /workspace/user_data/minicpm-vllm-omni/submission<br/>"
            "bash scripts/run_demo.sh<br/>"
            "bash scripts/benchmark_matrix.sh<br/>"
            "python3 scripts/validate_submission.py",
            styles["code"],
        )
    )
    story.append(
        p(
            "run_demo.sh 会记录配置哈希、服务健康状态、NPU 信息，执行文本到流式语音"
            "请求，并校验 WAV 的 24 kHz 单声道格式、时长和 SHA-256。每次运行写入独立"
            "时间戳目录，避免与旧 Demo 文件混用。",
            styles["body"],
        )
    )
    story.append(p("最终采用决定", styles["h2"]))
    decision = Table(
        [
            ["方案", "决定", "理由"],
            ["官方基线", "保留", "可读、可回退，是所有同机 A/B 的共同基准"],
            ["codec20", "淘汰", "核心 RTF、E2E 和吞吐同时退化"],
            ["steps9", "当前提交候选", "两次候选方向一致；Whisper proxy WER 一致；未校准 ASV proxy 配对差异不显著"],
        ],
        colWidths=[34 * mm, 34 * mm, 104 * mm],
        repeatRows=1,
    )
    decision.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), body_font),
                ("BACKGROUND", (0, 3), (-1, 3), PALE_TEAL),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, LIGHT_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(decision)
    story.append(Spacer(1, 6 * mm))
    story.append(
        p(
            "提交前仍需外部完成：录制实际可播放的 Demo 视频；在主办方最终环境运行"
            "正式 WER/ASV；正式赛事包补入完整服务日志；按平台最新要求核对文件命名、"
            "大小和截止时间。",
            styles["callout"],
        )
    )
    story.append(Spacer(1, 7 * mm))
    story.append(p("参考与附件", styles["h2"]))
    story.append(
        p(
            "赛事评测规范：https://modelbest.feishu.cn/docx/U41vdXMmQo7tv3xW2p9c9uEanKe<br/>"
            "官方 benchmark 配置：https://github.com/vllm-project/vllm-omni/blob/4a0a4817/"
            "tests/dfx/perf/tests/test_minicpmo_4_5.json<br/>"
            "详细数据：reports/EXPERIMENTS.md；ASV 边界：reports/ASV_PROXY.md；"
            "录屏清单：reports/SUBMISSION_CHECKLIST.md。",
            styles["small"],
        )
    )

    doc.build(story, onFirstPage=page_decor, onLaterPages=page_decor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "output"
        / "pdf"
        / "MiniCPM-o_4.5_Ascend_vLLM-Omni_Optimization_Report.pdf",
    )
    parser.add_argument("--font-dir", type=Path, default=Path("C:/Windows/Fonts"))
    args = parser.parse_args()
    build_report(args.output, args.font_dir)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
