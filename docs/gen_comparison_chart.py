"""Regenerates docs/comparison-{light,dark}.svg, the feature-comparison
chart embedded in README.md.

Usage: python3 docs/gen_comparison_chart.py docs

Edit the ROWS data below to update the chart, then re-run and commit the
resulting SVGs alongside this script.
"""

import html

TOOLS = ["YAC", "Hydra", "Medusa", "CredMaster", "TREVORspray", "MSOLSpray"]

# 2 = yes, 1 = partial/basic, 0 = no. Based on public documentation for each
# project; conservative where a capability isn't clearly documented.
ROWS = [
    ("Multi-target config (one run, many sites)", [2, 1, 1, 1, 1, 0]),
    ("Generic HTTP form login (CSRF-aware)",        [2, 1, 1, 0, 0, 0]),
    ("Real-browser login for JS/SPA forms",         [2, 0, 0, 0, 0, 0]),
    ("AI-agent (LLM) driven login",                 [2, 0, 0, 0, 0, 0]),
    ("Microsoft 365 / Azure AD (AADSTS-aware)",     [2, 0, 0, 2, 2, 2]),
    ("Okta (Authn API-aware)",                      [2, 0, 0, 2, 0, 0]),
    ("Lockout-aware pacing (per-account)",          [2, 0, 0, 1, 2, 0]),
    ("Password-spray ordering (wide-before-deep)",  [2, 1, 1, 2, 2, 2]),
    ("Bot/CAPTCHA detection + auto-abort",          [2, 0, 0, 0, 0, 0]),
    ("Resume after interruption",                   [2, 2, 0, 0, 0, 0]),
]

GLYPH = {2: "✓", 1: "◐", 0: "–"}  # check, half-circle, en-dash


def split_name(name):
    """Break a multi-word tool name at a real word boundary (camelCase or
    acronym-then-word), never mid-syllable."""
    candidates = []
    for i in range(1, len(name)):
        prev, cur = name[i - 1], name[i]
        if prev.islower() and cur.isupper():
            candidates.append(i)
        elif prev.isupper() and cur.islower() and i >= 2 and name[i - 2].isupper():
            candidates.append(i)
    if not candidates:
        mid = len(name) // 2 + 1
        return name[:mid], name[mid:]
    mid = len(name) / 2
    best = min(candidates, key=lambda i: abs(i - mid))
    return name[:best], name[best:]

def build(mode):
    dark = mode == "dark"
    surface   = "#1a1a19" if dark else "#fcfcfb"
    page      = "#0d0d0d" if dark else "#f9f9f7"
    ink       = "#ffffff" if dark else "#0b0b0b"
    ink2      = "#c3c2b7" if dark else "#52514e"
    muted     = "#898781"
    grid      = "#2c2c2a" if dark else "#e1e0d9"
    accent    = "#3987e5" if dark else "#2a78d6"
    accent_bg = "rgba(57,135,229,0.14)" if dark else "rgba(42,120,214,0.08)"
    accent_bg_head = "rgba(57,135,229,0.22)" if dark else "rgba(42,120,214,0.14)"

    feat_col_w = 350
    tool_col_w = 108
    n_tools = len(TOOLS)
    content_w = feat_col_w + tool_col_w * n_tools
    pad = 28
    title_h = 56
    header_h = 56
    row_h = 38
    footer_h = 34
    width = content_w + pad * 2
    height = pad + title_h + header_h + row_h * len(ROWS) + footer_h + pad

    x0 = pad
    y_title = pad
    y_header = y_title + title_h
    y_rows = y_header + header_h

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="system-ui,-apple-system,Segoe UI,sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="{page}"/>')
    parts.append(
        f'<rect x="{x0-16}" y="{y_title-8}" width="{content_w+32}" height="{height-y_title-pad+16}" '
        f'rx="12" fill="{surface}" stroke="{grid}" stroke-width="1"/>'
    )

    # Title
    parts.append(
        f'<text x="{x0}" y="{y_title+20}" font-size="19" font-weight="700" fill="{ink}">'
        f'YAC vs. alternative login-checker / password-spray tools</text>'
    )
    parts.append(
        f'<text x="{x0}" y="{y_title+40}" font-size="12.5" fill="{ink2}">'
        f'Feature coverage by project, based on each project’s public documentation</text>'
    )

    # YAC column emphasis band (spans header + rows)
    yac_x = x0 + feat_col_w
    parts.append(
        f'<rect x="{yac_x}" y="{y_header}" width="{tool_col_w}" height="{header_h + row_h*len(ROWS)}" '
        f'fill="{accent_bg}"/>'
    )
    parts.append(
        f'<rect x="{yac_x}" y="{y_header}" width="{tool_col_w}" height="{header_h}" fill="{accent_bg_head}"/>'
    )

    # Header row
    for i, tool in enumerate(TOOLS):
        cx = x0 + feat_col_w + tool_col_w * i + tool_col_w / 2
        is_yac = i == 0
        color = accent if is_yac else ink2
        weight = 700 if is_yac else 600
        # wrap long names onto two lines, at a real word boundary
        if len(tool) > 9:
            top, bottom = split_name(tool)
            parts.append(
                f'<text x="{cx}" y="{y_header + header_h/2 - 4}" font-size="12.5" font-weight="{weight}" '
                f'fill="{color}" text-anchor="middle">{html.escape(top)}</text>'
            )
            parts.append(
                f'<text x="{cx}" y="{y_header + header_h/2 + 12}" font-size="12.5" font-weight="{weight}" '
                f'fill="{color}" text-anchor="middle">{html.escape(bottom)}</text>'
            )
        else:
            parts.append(
                f'<text x="{cx}" y="{y_header + header_h/2 + 5}" font-size="13.5" font-weight="{weight}" '
                f'fill="{color}" text-anchor="middle">{html.escape(tool)}</text>'
            )
    parts.append(
        f'<line x1="{x0}" y1="{y_header+header_h}" x2="{x0+content_w}" y2="{y_header+header_h}" '
        f'stroke="{grid}" stroke-width="1.5"/>'
    )

    # Rows
    for r, (label, values) in enumerate(ROWS):
        ry = y_rows + row_h * r
        if r % 2 == 1:
            parts.append(f'<rect x="{x0}" y="{ry}" width="{content_w}" height="{row_h}" fill="{grid}" opacity="0.35"/>')
        parts.append(
            f'<text x="{x0+16}" y="{ry+row_h/2+5}" font-size="13" fill="{ink}">{html.escape(label)}</text>'
        )
        for i, v in enumerate(values):
            cx = x0 + feat_col_w + tool_col_w * i + tool_col_w / 2
            is_yac = i == 0
            if v == 2:
                color = accent if is_yac else ink2
                fs = "16"
            elif v == 1:
                color = accent if is_yac else muted
                fs = "14"
            else:
                color = muted
                fs = "14"
            parts.append(
                f'<text x="{cx}" y="{ry+row_h/2+5}" font-size="{fs}" fill="{color}" '
                f'text-anchor="middle" font-weight="{700 if (v==2 and is_yac) else 500}">{GLYPH[v]}</text>'
            )
        if r < len(ROWS) - 1:
            parts.append(
                f'<line x1="{x0}" y1="{ry+row_h}" x2="{x0+content_w}" y2="{ry+row_h}" '
                f'stroke="{grid}" stroke-width="1"/>'
            )

    # column separators
    for i in range(n_tools + 1):
        lx = x0 + feat_col_w + tool_col_w * i
        parts.append(
            f'<line x1="{lx}" y1="{y_header}" x2="{lx}" y2="{y_rows+row_h*len(ROWS)}" '
            f'stroke="{grid}" stroke-width="1"/>'
        )

    # Legend / footer
    fy = y_rows + row_h * len(ROWS) + 22
    legend = [(GLYPH[2], "supported"), (GLYPH[1], "partial / basic"), (GLYPH[0], "not supported")]
    lx = x0
    for glyph, label in legend:
        parts.append(f'<text x="{lx}" y="{fy}" font-size="13" fill="{ink2}" font-weight="600">{glyph}</text>')
        parts.append(f'<text x="{lx+16}" y="{fy}" font-size="11.5" fill="{muted}">{label}</text>')
        lx += 18 + len(label) * 6.6 + 22

    parts.append(
        f'<text x="{x0+content_w}" y="{fy}" font-size="11" fill="{muted}" text-anchor="end">'
        f'Sources: each project’s README/docs — verify current capabilities directly</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    with open(f"{out_dir}/comparison-light.svg", "w") as f:
        f.write(build("light"))
    with open(f"{out_dir}/comparison-dark.svg", "w") as f:
        f.write(build("dark"))
    print("done")
