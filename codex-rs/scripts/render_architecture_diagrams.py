#!/usr/bin/env python3
"""Render architecture/workflow diagrams for codex-rs as SVG and PNG.

The output is written to docs/architecture/.

This script intentionally uses only the Python standard library so it can run
inside constrained development environments. If `rsvg-convert` is available on
PATH, it also exports matching PNG files for each SVG.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "architecture"
FONT_STACK = "Inter, SF Pro Display, Segoe UI, Helvetica, Arial, sans-serif"


class Palette:
    background = "#f8fafc"
    border = "#cbd5e1"
    text = "#0f172a"
    muted = "#475569"
    soft = "#64748b"
    line = "#94a3b8"
    surface = "#ffffff"
    blue = "#dbeafe"
    blue_border = "#60a5fa"
    indigo = "#e0e7ff"
    indigo_border = "#818cf8"
    green = "#dcfce7"
    green_border = "#4ade80"
    amber = "#fef3c7"
    amber_border = "#f59e0b"
    rose = "#ffe4e6"
    rose_border = "#fb7185"
    violet = "#f3e8ff"
    violet_border = "#c084fc"
    cyan = "#cffafe"
    cyan_border = "#22d3ee"
    slate = "#e2e8f0"
    slate_border = "#94a3b8"


@dataclass
class BoxStyle:
    fill: str
    stroke: str
    title_fill: str = Palette.text
    body_fill: str = Palette.muted


@dataclass
class DiagramSpec:
    filename: str
    width: int
    height: int
    title: str
    subtitle: str
    drawer: callable


class SvgCanvas:
    def __init__(self, width: int, height: int, title: str, subtitle: str):
        self.width = width
        self.height = height
        self.title = title
        self.subtitle = subtitle
        self.elements: list[str] = []

    def add(self, raw: str) -> None:
        self.elements.append(raw)

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str = Palette.surface,
        stroke: str = Palette.border,
        rx: float = 20,
        ry: float | None = None,
        stroke_width: float = 1.5,
        dashed: bool = False,
    ) -> None:
        dash = ' stroke-dasharray="8 8"' if dashed else ""
        ry = rx if ry is None else ry
        self.add(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
            f'rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}"{dash} />'
        )

    def polygon(
        self,
        points: Iterable[tuple[float, float]],
        *,
        fill: str,
        stroke: str,
        stroke_width: float = 1.5,
    ) -> None:
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.add(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{stroke_width}" />'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: str = Palette.line,
        stroke_width: float = 2.5,
        marker_end: bool = False,
        dashed: bool = False,
    ) -> None:
        marker = ' marker-end="url(#arrow)"' if marker_end else ""
        dash = ' stroke-dasharray="8 8"' if dashed else ""
        self.add(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" '
            f'stroke-linecap="round"{marker}{dash} />'
        )

    def polyline(
        self,
        points: Iterable[tuple[float, float]],
        *,
        stroke: str = Palette.line,
        stroke_width: float = 2.5,
        marker_end: bool = True,
        dashed: bool = False,
    ) -> None:
        pts = " ".join(f"{x},{y}" for x, y in points)
        marker = ' marker-end="url(#arrow)"' if marker_end else ""
        dash = ' stroke-dasharray="8 8"' if dashed else ""
        self.add(
            f'<polyline points="{pts}" fill="none" stroke="{stroke}" '
            f'stroke-width="{stroke_width}" stroke-linecap="round" '
            f'stroke-linejoin="round"{marker}{dash} />'
        )

    def text(
        self,
        x: float,
        y: float,
        text: str,
        *,
        size: int = 18,
        fill: str = Palette.text,
        weight: int = 400,
        anchor: str = "start",
        family: str = FONT_STACK,
        letter_spacing: float = 0,
    ) -> None:
        content = escape(text)
        self.add(
            f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
            f'letter-spacing="{letter_spacing}">{content}</text>'
        )

    def text_block(
        self,
        x: float,
        y: float,
        text: str,
        *,
        width: float,
        size: int = 18,
        fill: str = Palette.muted,
        weight: int = 400,
        anchor: str = "start",
        family: str = FONT_STACK,
        line_height: float = 1.35,
    ) -> None:
        chars = max(10, int(width / max(5.5, size * 0.56)))
        lines: list[str] = []
        for raw_line in text.split("\n"):
            stripped = raw_line.rstrip()
            if not stripped:
                lines.append("")
                continue
            if stripped.startswith("• "):
                bullet = stripped[:2]
                rest = stripped[2:]
                wrapped = textwrap.wrap(
                    rest,
                    width=max(8, chars - 2),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                if not wrapped:
                    lines.append(bullet)
                else:
                    lines.append(f"{bullet}{wrapped[0]}")
                    lines.extend(f"  {line}" for line in wrapped[1:])
                continue
            wrapped = textwrap.wrap(
                stripped,
                width=chars,
                break_long_words=False,
                break_on_hyphens=False,
            )
            lines.extend(wrapped or [""])

        if not lines:
            lines = [""]

        attrs = (
            f'x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"'
        )
        tspan_x = x
        dy = size * line_height
        tspans = [f'<tspan x="{tspan_x}" dy="0">{escape(lines[0])}</tspan>']
        for line in lines[1:]:
            tspans.append(f'<tspan x="{tspan_x}" dy="{dy}">{escape(line)}</tspan>')
        self.add(f'<text {attrs}>{"".join(tspans)}</text>')

    def label(
        self,
        x: float,
        y: float,
        text: str,
        *,
        fill: str = Palette.soft,
        size: int = 16,
        anchor: str = "middle",
        background: str | None = Palette.background,
    ) -> None:
        text = escape(text)
        if background:
            width = max(42, len(text) * size * 0.55)
            self.rect(
                x - width / 2 - 10,
                y - size,
                width + 20,
                size + 18,
                fill=background,
                stroke="none",
                rx=14,
                stroke_width=0,
            )
        self.text(x, y + 3, text, size=size, fill=fill, anchor=anchor, weight=600)

    def card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        *,
        style: BoxStyle,
        title_size: int = 22,
        body_size: int = 17,
        title_family: str = FONT_STACK,
    ) -> None:
        self.rect(x, y, w, h, fill=style.fill, stroke=style.stroke)
        self.text(x + 18, y + 34, title, size=title_size, fill=style.title_fill, weight=700, family=title_family)
        self.text_block(
            x + 18,
            y + 66,
            body,
            width=w - 36,
            size=body_size,
            fill=style.body_fill,
            line_height=1.38,
        )

    def lane(self, x: float, y: float, w: float, h: float, title: str, *, fill: str = "#f1f5f9") -> None:
        self.rect(x, y, w, h, fill=fill, stroke=Palette.border, rx=28)
        self.text(x + w / 2, y + 36, title, size=22, weight=800, fill=Palette.text, anchor="middle")
        self.line(x + 24, y + 52, x + w - 24, y + 52, stroke=Palette.border, stroke_width=1.5)

    def render(self) -> str:
        defs = f"""
<defs>
  <marker id="arrow" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto">
    <path d="M0,0 L12,6 L0,12 z" fill="{Palette.line}" />
  </marker>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
    <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#0f172a" flood-opacity="0.08" />
  </filter>
</defs>
""".strip()
        bg = f'<rect x="0" y="0" width="{self.width}" height="{self.height}" fill="{Palette.background}" />'
        header = [
            bg,
            defs,
            f'<g filter="url(#shadow)">',
            f'<rect x="32" y="28" width="{self.width - 64}" height="{self.height - 56}" rx="32" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.5" />',
            "</g>",
        ]
        title_y = 78
        subtitle_y = 114
        header.append(
            f'<text x="64" y="{title_y}" font-family="{FONT_STACK}" font-size="34" font-weight="800" fill="{Palette.text}">{escape(self.title)}</text>'
        )
        header.append(
            f'<text x="64" y="{subtitle_y}" font-family="{FONT_STACK}" font-size="18" font-weight="400" fill="{Palette.muted}">{escape(self.subtitle)}</text>'
        )
        body = "\n".join(header + self.elements)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}">\n{body}\n</svg>\n'
        )


def diamond_points(cx: float, cy: float, w: float, h: float) -> list[tuple[float, float]]:
    return [
        (cx, cy - h / 2),
        (cx + w / 2, cy),
        (cx, cy + h / 2),
        (cx - w / 2, cy),
    ]


def draw_feature_map(svg: SvgCanvas) -> None:
    y = 150
    svg.card(
        70,
        y,
        360,
        220,
        "User-facing surfaces",
        "• codex (multitool CLI)\n• codex-tui (interactive TUI)\n• codex-exec (headless automation)\n• codex app-server (JSON-RPC server)\n• codex mcp-server (Codex as an MCP tool)",
        style=BoxStyle(Palette.blue, Palette.blue_border),
    )
    svg.card(
        470,
        y,
        360,
        220,
        "Control plane",
        "• codex-app-server-client unifies in-process and remote clients\n• codex-app-server exposes thread / turn / item APIs\n• app-server-protocol defines JSON-RPC v2 contracts\n• protocol keeps the legacy Op / Event core types",
        style=BoxStyle(Palette.indigo, Palette.indigo_border),
    )
    svg.card(
        870,
        y,
        360,
        220,
        "Core runtime",
        "• ThreadManager owns live threads\n• CodexThread wraps a session handle\n• Session manages turn state, mailbox, tools, history, hooks\n• tasks::RegularTask drives the normal run_turn loop",
        style=BoxStyle(Palette.green, Palette.green_border),
    )
    svg.card(
        1270,
        y,
        400,
        220,
        "Providers and transports",
        "• codex-api builds typed Responses / Compact / Memories requests\n• codex-client owns HTTP/SSE/WebSocket transport details\n• login + models-manager select OpenAI, ChatGPT, LM Studio, or Ollama",
        style=BoxStyle(Palette.cyan, Palette.cyan_border),
    )

    svg.card(
        70,
        420,
        520,
        230,
        "Extensibility features",
        "• skills and core-skills inject task-specific instructions\n• plugins add packaged skills, apps, MCP servers, and marketplace metadata\n• MCP client support loads tools/resources/templates from external servers\n• dynamic tools and multi-agent tools extend the model-visible tool set at runtime",
        style=BoxStyle(Palette.violet, Palette.violet_border),
    )
    svg.card(
        640,
        420,
        520,
        230,
        "Execution and safety features",
        "• approval policies decide when the user (or guardian) must approve tool actions\n• sandboxing selects read-only / workspace-write / danger-full-access enforcement\n• execpolicy and shell-escalation shape command execution\n• network-proxy applies domain and socket policies",
        style=BoxStyle(Palette.amber, Palette.amber_border),
    )
    svg.card(
        1210,
        420,
        460,
        230,
        "Persistence and observability",
        "• rollout JSONL files under ~/.codex/sessions keep the source-of-truth transcript\n• codex-state mirrors searchable metadata into SQLite\n• otel, analytics, and feedback crates emit logs, traces, metrics, and support bundles",
        style=BoxStyle(Palette.rose, Palette.rose_border),
    )

    svg.card(
        290,
        700,
        1140,
        250,
        "Main end-to-end path",
        "Surface -> app-server client / transport -> app-server message processor -> ThreadManager -> Session task -> ModelClient -> provider stream. During the turn, ToolRouter and the orchestrator can branch into approvals, sandbox selection, command execution, patch application, MCP calls, app tools, or multi-agent fan-out before their outputs are fed back into the next model sampling round.",
        style=BoxStyle(Palette.slate, Palette.slate_border),
        title_size=24,
        body_size=19,
    )

    svg.polyline([(430, 260), (470, 260)], marker_end=True)
    svg.polyline([(830, 260), (870, 260)], marker_end=True)
    svg.polyline([(1230, 260), (1270, 260)], marker_end=True)
    svg.polyline([(1030, 370), (1030, 700)], marker_end=True)
    svg.polyline([(330, 650), (520, 700)], marker_end=True)
    svg.polyline([(900, 650), (850, 700)], marker_end=True)
    svg.polyline([(1450, 650), (1240, 700)], marker_end=True)
    svg.label(450, 734, "shared API / client contract")
    svg.label(1000, 734, "session + turn execution")
    svg.label(1370, 734, "provider streaming")
    svg.text(
        850,
        1000,
        "Thread = conversation boundary   •   Turn = one user-driven execution cycle   •   Item = persisted unit of input or output",
        size=20,
        fill=Palette.soft,
        anchor="middle",
        weight=600,
    )


def draw_main_workflow(svg: SvgCanvas) -> None:
    box_w = 250
    box_h = 118
    y = 210
    x_positions = [80, 365, 650, 935, 1220, 1505]
    titles = [
        "1. User prompt",
        "2. codex CLI",
        "3. TUI bootstrap",
        "4. App server",
        "5. Core runtime",
        "6. Model + tools",
    ]
    bodies = [
        "Prompt, images, cwd, and mode selection enter through the codex command.",
        "cli/src/main.rs parses flags and chooses TUI, exec, app-server, or mcp-server.",
        "codex_tui::run_main loads config, runs onboarding/trust checks, and starts an embedded or remote app-server session.",
        "bootstrap requests load account + model catalog, then thread/start or resume/fork establishes the thread.",
        "turn/start becomes core ops, a Session spawns RegularTask, and run_turn builds prompt + tools for each sampling round.",
        "The provider streams assistant items or tool calls; tools may branch into approvals, sandboxed execution, patches, MCP, apps, or sub-agents.",
    ]
    styles = [
        BoxStyle(Palette.blue, Palette.blue_border),
        BoxStyle(Palette.indigo, Palette.indigo_border),
        BoxStyle(Palette.violet, Palette.violet_border),
        BoxStyle(Palette.green, Palette.green_border),
        BoxStyle(Palette.amber, Palette.amber_border),
        BoxStyle(Palette.cyan, Palette.cyan_border),
    ]
    for x, title, body, style in zip(x_positions, titles, bodies, styles):
        svg.card(x, y, box_w, box_h, title, body, style=style, title_size=20, body_size=15)
    for i in range(len(x_positions) - 1):
        svg.polyline(
            [(x_positions[i] + box_w, y + box_h / 2), (x_positions[i + 1], y + box_h / 2)],
            marker_end=True,
        )

    svg.card(
        110,
        410,
        540,
        180,
        "7. Notifications stream back",
        "item/started, item/.../delta, item/completed, turn/started, turn/completed, warnings, approval requests, and status notifications flow back through the app-server adapter and update the TUI state in real time.",
        style=BoxStyle(Palette.green, Palette.green_border),
        title_size=22,
        body_size=17,
    )
    svg.card(
        760,
        410,
        510,
        180,
        "8. Persistence and resumability",
        "Each turn writes rollout JSONL records, while codex-state maintains SQLite metadata so thread/list, read, archive, and resume can stay fast without losing the append-only source transcript.",
        style=BoxStyle(Palette.rose, Palette.rose_border),
        title_size=22,
        body_size=17,
    )
    svg.card(
        1360,
        410,
        260,
        180,
        "9. Final output",
        "The user sees rendered assistant text, diffs, approvals, status, token usage, and a resumable thread id/name.",
        style=BoxStyle(Palette.slate, Palette.slate_border),
        title_size=22,
        body_size=17,
    )

    svg.polyline([(1630, 268), (1630, 360), (380, 360), (380, 410)], marker_end=True)
    svg.polyline([(1630, 268), (1630, 360), (1015, 360), (1015, 410)], marker_end=True)
    svg.polyline([(380, 590), (380, 690), (1490, 690), (1490, 590)], marker_end=True)

    svg.card(
        110,
        690,
        610,
        220,
        "Turn loop details",
        "Inside one turn, core may perform multiple model sampling rounds. Tool outputs, extra pending input, hook continuations, compaction, or interruptions can all cause another internal request before the turn finally completes.",
        style=BoxStyle(Palette.amber, Palette.amber_border),
        title_size=24,
        body_size=18,
    )
    svg.card(
        810,
        690,
        560,
        220,
        "Embedded versus remote app-server",
        "TUI usually starts an in-process app-server through codex-app-server-client, but the same UI contract can target a remote websocket app-server. That keeps local and remote behavior aligned around the same thread/turn API.",
        style=BoxStyle(Palette.cyan, Palette.cyan_border),
        title_size=24,
        body_size=18,
    )
    svg.card(
        1420,
        690,
        210,
        220,
        "Related surfaces",
        "codex-exec follows the same app-server path without the fullscreen TUI. mcp-server turns Codex itself into a tool for other MCP clients.",
        style=BoxStyle(Palette.violet, Palette.violet_border),
        title_size=24,
        body_size=16,
    )


def draw_turn_loop(svg: SvgCanvas) -> None:
    svg.card(
        120,
        170,
        360,
        110,
        "Start turn",
        "RegularTask emits TurnStarted and checks whether there is initial or pending input to consume.",
        style=BoxStyle(Palette.blue, Palette.blue_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        120,
        320,
        360,
        120,
        "Prepare context",
        "Run pre-sampling compact if needed, record turn context updates, and establish the history reference point for the sampling round.",
        style=BoxStyle(Palette.indigo, Palette.indigo_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        120,
        485,
        360,
        150,
        "Collect runtime capabilities",
        "Load skill injections, plugin mentions, MCP tool inventory, connector/app visibility, dynamic tools, and collaboration-mode instructions for this turn.",
        style=BoxStyle(Palette.violet, Palette.violet_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        120,
        675,
        360,
        120,
        "Build prompt + ToolRouter",
        "Prompt = history + instructions + model settings + current tool specs. ToolRouter decides what tools the model can call this round.",
        style=BoxStyle(Palette.green, Palette.green_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        120,
        835,
        360,
        120,
        "Run sampling request",
        "ModelClient streams Responses events. Core converts them into item starts, deltas, completions, warnings, and tool futures.",
        style=BoxStyle(Palette.cyan, Palette.cyan_border),
        title_size=22,
        body_size=16,
    )
    svg.line(300, 280, 300, 320, marker_end=True)
    svg.line(300, 440, 300, 485, marker_end=True)
    svg.line(300, 635, 300, 675, marker_end=True)
    svg.line(300, 795, 300, 835, marker_end=True)

    svg.polygon(
        diamond_points(790, 280, 260, 120),
        fill=Palette.amber,
        stroke=Palette.amber_border,
    )
    svg.text(790, 270, "Tool call", size=24, weight=700, anchor="middle")
    svg.text(790, 302, "present?", size=22, weight=700, anchor="middle")

    svg.polygon(
        diamond_points(790, 520, 300, 140),
        fill=Palette.rose,
        stroke=Palette.rose_border,
    )
    svg.text(790, 505, "Need approval", size=24, weight=700, anchor="middle")
    svg.text(790, 538, "or policy change?", size=22, weight=700, anchor="middle")

    svg.card(
        1090,
        200,
        420,
        140,
        "Assistant-only path",
        "Record assistant / reasoning items, update token usage, and keep any streamed deltas visible to the client.",
        style=BoxStyle(Palette.green, Palette.green_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        1090,
        420,
        420,
        170,
        "Tool execution path",
        "Orchestrator applies approvals, chooses sandbox mode, runs shell / patch / MCP / app / dynamic / multi-agent tools, then records outputs as pending input for a follow-up sampling round.",
        style=BoxStyle(Palette.cyan, Palette.cyan_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        1090,
        675,
        420,
        130,
        "Post-round checks",
        "Inspect pending input, stop hooks, interrupts, errors, and auto-compact thresholds before deciding whether another round is needed.",
        style=BoxStyle(Palette.indigo, Palette.indigo_border),
        title_size=22,
        body_size=16,
    )

    svg.polygon(
        diamond_points(790, 760, 300, 140),
        fill=Palette.violet,
        stroke=Palette.violet_border,
    )
    svg.text(790, 745, "More pending input", size=23, weight=700, anchor="middle")
    svg.text(790, 778, "or follow-up work?", size=21, weight=700, anchor="middle")

    svg.card(
        1090,
        870,
        420,
        120,
        "Turn completes",
        "Emit TurnComplete, clear active turn state, persist rollout items, and allow the scheduler to start the next queued turn if one exists.",
        style=BoxStyle(Palette.slate, Palette.slate_border),
        title_size=22,
        body_size=16,
    )

    svg.polyline([(480, 895), (610, 895), (610, 280), (660, 280)], marker_end=True)
    svg.polyline([(920, 280), (1090, 280)], marker_end=True)
    svg.polyline([(790, 340), (790, 450)], marker_end=True)
    svg.polyline([(920, 520), (1090, 520)], marker_end=True)
    svg.polyline([(1300, 590), (1300, 740), (940, 740)], marker_end=True)
    svg.polyline([(1300, 340), (1300, 740), (940, 740)], marker_end=True)
    svg.polyline([(790, 590), (790, 675)], marker_end=True)
    svg.polyline([(920, 760), (1090, 760)], marker_end=True)
    svg.polyline([(790, 830), (790, 895), (1090, 930)], marker_end=True)
    svg.polyline([(640, 760), (300, 760), (300, 835)], marker_end=True)

    svg.label(1020, 258, "no")
    svg.label(970, 498, "yes")
    svg.label(1020, 738, "no")
    svg.label(470, 738, "yes -> loop")

    svg.text_block(
        100,
        1010,
        "Key idea: one user-visible turn may contain multiple internal model requests. The loop ends only when there is no pending input, no required follow-up, and no stop-hook continuation blocking completion.",
        width=1460,
        size=18,
        fill=Palette.soft,
    )


def draw_control_plane(svg: SvgCanvas) -> None:
    svg.lane(70, 160, 420, 860, "Surfaces")
    svg.lane(550, 160, 420, 860, "Shared control plane")
    svg.lane(1030, 160, 360, 860, "Core runtime")
    svg.lane(1450, 160, 280, 860, "Providers / state")

    svg.card(
        105,
        220,
        350,
        140,
        "codex-tui",
        "Interactive fullscreen UI. Uses AppServerSession and the app-server adapter to drive a thread and render live notifications.",
        style=BoxStyle(Palette.blue, Palette.blue_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        105,
        390,
        350,
        140,
        "codex-exec",
        "Headless automation surface. Starts an in-process app-server client and renders either human text or JSONL events.",
        style=BoxStyle(Palette.indigo, Palette.indigo_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        105,
        560,
        350,
        160,
        "Remote clients",
        "VS Code, websocket integrations, app-server test clients, and other tooling connect through the same thread / turn / item contract.",
        style=BoxStyle(Palette.violet, Palette.violet_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        105,
        750,
        350,
        180,
        "mcp-server consumers",
        "Other MCP clients can run Codex itself as a tool server; internally, that still converges on the same core engine concepts.",
        style=BoxStyle(Palette.cyan, Palette.cyan_border),
        title_size=22,
        body_size=16,
    )

    svg.card(
        585,
        230,
        350,
        130,
        "codex-app-server-client",
        "TUI and exec use the same facade for in-process startup, typed requests, notifications, and bounded shutdown.",
        style=BoxStyle(Palette.green, Palette.green_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        585,
        400,
        350,
        180,
        "codex-app-server",
        "Transport + routing layer. Handles initialize, thread/start, turn/start, approvals, config APIs, FS APIs, and connection/session state.",
        style=BoxStyle(Palette.amber, Palette.amber_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        585,
        630,
        350,
        170,
        "MessageProcessor stack",
        "MessageProcessor wires auth/config/fs helpers. CodexMessageProcessor converts app-server requests into core thread and turn operations.",
        style=BoxStyle(Palette.rose, Palette.rose_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        585,
        840,
        350,
        130,
        "Thread watch + bespoke event handling",
        "Live core events are rewritten into app-server thread/turn/item notifications and request/response flows.",
        style=BoxStyle(Palette.slate, Palette.slate_border),
        title_size=22,
        body_size=16,
    )

    svg.card(
        1065,
        260,
        290,
        150,
        "ThreadManager",
        "Owns live thread registry, spawning, resume/fork logic, watchers, and thread lifecycle.",
        style=BoxStyle(Palette.green, Palette.green_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        1065,
        450,
        290,
        170,
        "CodexThread + Session",
        "Submission queue, event queue, active turn state, mailbox, hooks, history, MCP manager, plugins, and task scheduling.",
        style=BoxStyle(Palette.blue, Palette.blue_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        1065,
        670,
        290,
        180,
        "Tasks + tool orchestration",
        "RegularTask / review / compact / user_shell call run_turn, build the prompt, and broker tool execution with approval and sandbox policies.",
        style=BoxStyle(Palette.indigo, Palette.indigo_border),
        title_size=22,
        body_size=16,
    )

    svg.card(
        1485,
        260,
        210,
        140,
        "Model providers",
        "OpenAI / ChatGPT / LM Studio / Ollama via codex-api + codex-client.",
        style=BoxStyle(Palette.cyan, Palette.cyan_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        1485,
        470,
        210,
        160,
        "Persistence",
        "Rollout JSONL sessions + codex-state SQLite metadata and logs.",
        style=BoxStyle(Palette.rose, Palette.rose_border),
        title_size=22,
        body_size=16,
    )
    svg.card(
        1485,
        700,
        210,
        180,
        "Policy + telemetry",
        "login, models-manager, sandboxing, execpolicy, network-proxy, otel, analytics, feedback.",
        style=BoxStyle(Palette.amber, Palette.amber_border),
        title_size=22,
        body_size=16,
    )

    # Surface -> control plane
    for y in [290, 460, 640, 840]:
        svg.polyline([(455, y), (585, y)], marker_end=True)
    svg.label(520, 265, "embedded or remote")

    # Control plane -> core
    svg.polyline([(935, 295), (1065, 335)], marker_end=True)
    svg.polyline([(935, 490), (1065, 535)], marker_end=True)
    svg.polyline([(935, 715), (1065, 535)], marker_end=True)
    svg.polyline([(935, 905), (1065, 760)], marker_end=True)

    # Core -> providers/state
    svg.polyline([(1355, 335), (1485, 330)], marker_end=True)
    svg.polyline([(1355, 535), (1485, 550)], marker_end=True)
    svg.polyline([(1355, 760), (1485, 790)], marker_end=True)

    # feedback arrows back
    svg.polyline([(1485, 550), (1425, 550), (1425, 535), (1355, 535)], marker_end=True, dashed=True)
    svg.polyline([(1485, 790), (1425, 790), (1425, 760), (1355, 760)], marker_end=True, dashed=True)
    svg.label(1410, 518, "events / metadata")
    svg.label(1410, 734, "policy inputs")

    svg.text_block(
        120,
        980,
        "Why this layering matters: local TUI, local exec, and remote integrations all converge on the app-server contract. That lets Codex share one thread/turn model across transports while still keeping the heavy runtime logic in codex-core.",
        width=1540,
        size=18,
        fill=Palette.soft,
    )


def write_readme() -> None:
    readme = OUT_DIR / "README.md"
    readme.write_text(
        "# codex-rs architecture diagrams\n\n"
        "Generated files in this directory:\n\n"
        "- `codex-rs-feature-map.{svg,png}`\n"
        "- `codex-rs-main-workflow.{svg,png}`\n"
        "- `codex-rs-turn-execution-loop.{svg,png}`\n"
        "- `codex-rs-control-plane.{svg,png}`\n\n"
        "Regenerate them from `codex-rs/` with:\n\n"
        "```bash\n"
        "python3 scripts/render_architecture_diagrams.py\n"
        "```\n",
        encoding="utf-8",
    )


def export_png(svg_path: Path) -> None:
    converter = shutil.which("rsvg-convert")
    if not converter:
        return
    png_path = svg_path.with_suffix(".png")
    subprocess.run(
        [converter, str(svg_path), "-o", str(png_path)],
        check=True,
        cwd=ROOT,
    )


def render_diagram(spec: DiagramSpec) -> None:
    canvas = SvgCanvas(spec.width, spec.height, spec.title, spec.subtitle)
    spec.drawer(canvas)
    svg_path = OUT_DIR / f"{spec.filename}.svg"
    svg_path.write_text(canvas.render(), encoding="utf-8")
    export_png(svg_path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    specs = [
        DiagramSpec(
            filename="codex-rs-feature-map",
            width=1760,
            height=1080,
            title="codex-rs feature map",
            subtitle="Major surfaces, runtime layers, safety systems, extension points, and storage/telemetry responsibilities.",
            drawer=draw_feature_map,
        ),
        DiagramSpec(
            filename="codex-rs-main-workflow",
            width=1760,
            height=980,
            title="codex-rs main interactive workflow",
            subtitle="From `codex` command entry to thread startup, turn execution, notifications, persistence, and final output.",
            drawer=draw_main_workflow,
        ),
        DiagramSpec(
            filename="codex-rs-turn-execution-loop",
            width=1600,
            height=1100,
            title="codex-rs turn execution loop",
            subtitle="How a regular core turn prepares context, streams model output, runs tools, and decides whether another sampling round is needed.",
            drawer=draw_turn_loop,
        ),
        DiagramSpec(
            filename="codex-rs-control-plane",
            width=1800,
            height=1080,
            title="codex-rs control plane and runtime layering",
            subtitle="How TUI, exec, remote clients, app-server, and codex-core align around the same thread/turn model.",
            drawer=draw_control_plane,
        ),
    ]
    for spec in specs:
        render_diagram(spec)
    write_readme()
    print(f"Wrote diagrams to {OUT_DIR}")


if __name__ == "__main__":
    main()
