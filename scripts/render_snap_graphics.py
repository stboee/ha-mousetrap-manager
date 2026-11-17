"""Build original vector illustrations from the user's trap photo references.

No photographs, manufacturer artwork or logos are embedded. GPL-3.0-or-later.
The status badge describes the integration's status, not proven physical arming.
Run with Python's standard library; generated SVGs are shipped with the integration.
"""

from pathlib import Path

IMAGES = Path(__file__).resolve().parents[1] / "custom_components/mousetrap_manager/frontend/images"
STATES = {
    "normal": ("Overvåking aktiv", "#246c47"),
    "pending": ("Må kontrolleres", "#986000"),
    "inspection": ("Tid for inspeksjon", "#986000"),
    "unavailable": ("Utilgjengelig", "#495465"),
}

DEFS = """
  <linearGradient id="rapp-side" x2=".2" y2="1">
    <stop stop-color="#544b48"/><stop offset="1" stop-color="#29272a"/>
  </linearGradient>
  <linearGradient id="rapp-top" x2=".4" y2="1">
    <stop stop-color="#6e6d68"/><stop offset="1" stop-color="#373a38"/>
  </linearGradient>
  <linearGradient id="ivory" x2="1" y2=".4">
    <stop stop-color="#f1f0e5"/><stop offset=".6" stop-color="#dedfd4"/>
    <stop offset="1" stop-color="#c8cbc2"/>
  </linearGradient>
  <linearGradient id="metal" x2=".7" y2="1">
    <stop stop-color="#68737b"/><stop offset=".35" stop-color="#eef1ec"/>
    <stop offset=".55" stop-color="#a5aaa7"/><stop offset=".8" stop-color="#fafbf6"/>
    <stop offset="1" stop-color="#737d83"/>
  </linearGradient>
  <filter id="muted" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/></filter>
"""


def rapp(pending):
    gate = (
        '<path d="m49 85 57 13-10 37-55-18Z" fill="#575654" stroke="#777a73"/>'
        '<path d="m44 116 52 17" stroke="#a3a5a0" stroke-width="3"/>'
        if pending
        else '<path d="m48 116 49 15 7-12-49-15Z" fill="#313638" stroke="#636864"/>'
        '<path d="m60 118 32 9" stroke="#969b95" stroke-width="2"/>'
    )
    lever = (
        '<path d="m85 70 107-31 64 4-8 9-54-4-101 32Z" fill="url(#rapp-top)" stroke="#858780"/>'
        if pending
        else '<path d="m82 61 105-29q12-3 24-1l58 3-9 10-52-3q-9-1-17 2L91 73Z" '
        'fill="url(#rapp-top)" stroke="#858780" stroke-width="1.5"/>'
    )
    return f"""
  <path d="m24 130 81 28 201-40-3 6-198 40-83-29Z" fill="#25262a" stroke="#73716d"/>
  <path d="m119 83 158-39 29 73-200 41Z" fill="url(#rapp-side)" stroke="#292a2b" stroke-width="2"/>
  <path d="m43 68 140-34 94 10-158 39Z" fill="url(#rapp-top)" stroke="#85847c"/>
  <path d="m43 68 76 15-13 75-82-28Z" fill="#4d4644" stroke="#77736d" stroke-width="1.5"/>
  <path d="m50 79 56 14-10 46-58-20Z" fill="#11171a" stroke="#777972" stroke-width="2"/>
  <path d="m52 81-7 34 13-4 8-27Z" fill="#22282b"/>
  <path d="m67 98 32 9-4 16-31-10Z" fill="#070d11"/>
  {gate}
  <path d="m132 92 138-34 23 55-171 36Z" fill="none" stroke="#79706a" stroke-opacity=".38"/>
  <path d="m112 148 185-38" stroke="#8f8276" stroke-opacity=".4"/>
  <path d="m52 70 65 13 149-36" fill="none" stroke="#9c9589" stroke-opacity=".6"/>
  {lever}
  <path d="m96 72 12 7-5 30" fill="none" stroke="#111a1e" stroke-width="5"/>
  <path d="m85 65-9 26" fill="none" stroke="#969892" stroke-width="3"/>
  <path d="M90 64q-7-4-15 2l-11 10q-6 7-2 15t15 4l13-9q8-9 0-22Z"
    fill="#343937" stroke="#6f756e" stroke-width="1.5"/>
  <path d="m66 88 18-14" stroke="#171d1c" stroke-width="2"/>
  <ellipse cx="226" cy="80" rx="3.5" ry="5" transform="rotate(-12 226 80)"
    fill="#373230" stroke="#706861"/>
"""


def giljotin(pending):
    gate = (
        '<path d="m48 78 61 16v43l-61-18Z" fill="#666e72" stroke="#9aa3a5"/>'
        '<path d="m49 117 58 17" stroke="url(#metal)" stroke-width="3"/>'
        if pending
        else '<path d="m48 76 61 17v13L48 89Z" fill="#3b454d" stroke="#7d8990"/>'
    )
    slots = "".join(
        f'<path d="m{x} {y}v{h}" stroke="#b8bcb5" stroke-width="8" stroke-linecap="round"/>'
        f'<path d="m{x + 1} {y + 1}v{h - 2}" stroke="#4c5658" stroke-width="4.5" stroke-linecap="round"/>'
        for x, y, h in ((155, 78, 49), (177, 71, 48), (199, 64, 47), (221, 57, 46), (243, 50, 45), (265, 43, 44))
    )
    lever = (
        '<path d="m76 71 103-39 20 8-95 39Z" fill="#3c4751" stroke="#74808a" stroke-width="1.5"/>'
        if pending
        else '<path d="m68 70 89-49q7-4 13 0l12 7-100 51Z" fill="#414c56" stroke="#7c8791" stroke-width="1.5"/>'
    )
    return f"""
  <path d="m24 128 91 30 190-43v8l-190 44-91-31Z" fill="#343e48" stroke="#6d7982"/>
  <path d="m33 124 87 27 176-42-82-23Z" fill="#4d5861" stroke="#7e898e"/>
  <path d="m44 119 72 23 33-8-73-23Z" fill="#1b252d"/>
  <path d="m54 118 59 18m-42-23 59 18m-42-23 59 18" stroke="#788282" stroke-width="3"/>
  <path d="m118 66 162-37 13 8v76l-175 40Z" fill="url(#ivory)" stroke="#969f9b" stroke-width="1.5"/>
  <path d="m118 66 162-37 13 8-162 39Z" fill="#f8f7ee" stroke="#c8cbc2"/>
  {slots}
  <path d="m37 62 13 3 1 60-14-5Z" fill="#ececdf" stroke="#a4aba6" stroke-width="1.3"/>
  <path d="m30 67 7-5v58l-7 6Z" fill="#c2c7bf" stroke="#a4aba6"/>
  <path d="m49 77 64 17v44l-64-20Z" fill="#202a31"/>
  {gate}
  <path d="m36 70 79 21 1 9-80-22Z" fill="#f6f5e9" stroke="#b2b9b0"/>
  <path d="m109 84 12-9 12 2v76l-17 4-7-5Z" fill="#eaeadd" stroke="#a6aea6" stroke-width="1.4"/>
  <path d="m121 80 11-3v75l-11 3" fill="#f7f5e9"/>
  <path d="m48 128 65 20" stroke="#c6cdc2" stroke-width="2"/>
  <path d="m84 90 102-51" fill="none" stroke="#6e787a" stroke-width="5"/>
  <path d="m84 89 102-51" fill="none" stroke="url(#metal)" stroke-width="3"/>
  {lever}
  <path d="m177 63 6-39q2-10 9-12l22-6q19-4 22 11l7 27"
    fill="none" stroke="#68716f" stroke-width="5"/>
  <path d="m177 62 6-38q2-10 9-12l22-6q19-4 22 11l7 27"
    fill="none" stroke="url(#metal)" stroke-width="3"/>
  <ellipse cx="212" cy="33" rx="18" ry="29" transform="rotate(22 212 33)"
    fill="none" stroke="#5d6768" stroke-width="5"/>
  <ellipse cx="212" cy="32" rx="18" ry="29" transform="rotate(22 212 32)"
    fill="none" stroke="url(#metal)" stroke-width="3"/>
  <path d="m163 56 5-24 12-3 4 21" fill="#414b54" stroke="#707c84"/>
  <path d="m161 60 18-5 6 4v9l-17 5-7-4Z" fill="#414b54" stroke="#818d91"/>
  <path d="m87 93 14 4-2 7-14-4Z" fill="#3c4650" stroke="#7c8990"/>
"""


def render(model, state):
    label, color = STATES[state]
    name = "Rapp 2" if model == "rapp-2" else "Biltema Giljotin"
    shape = rapp(state == "pending") if model == "rapp-2" else giljotin(state == "pending")
    symbols = {
        "normal": '<path d="m-11 0 7 7 15-16" fill="none" stroke="white" stroke-width="4.5"/>',
        "pending": '<text y="13" text-anchor="middle" fill="white" font-family="sans-serif" '
        'font-size="37" font-weight="bold">?</text>',
        "inspection": '<path d="m0-16 16 28h-32Z" fill="none" stroke="white" stroke-width="3"/>'
        '<path d="M0-6v8M0 7v1" stroke="white" stroke-width="3.5"/>',
        "unavailable": '<path d="m-9-9 18 18m0-18-18 18" fill="none" stroke="white" stroke-width="4"/>',
    }
    muted = ' filter="url(#muted)" opacity=".48"' if state == "unavailable" else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 180" width="1080" height="540"
  role="img" aria-labelledby="title">
  <title id="title">{name} – {label}</title>
  <defs>{DEFS}</defs>
  <ellipse cx="168" cy="167" rx="146" ry="5" fill="{color}" opacity=".13"/>
  <g stroke-linejoin="round" stroke-linecap="round"{muted}>{shape}</g>
  <g transform="translate(326 34)" stroke-linejoin="round" stroke-linecap="round">
    <circle r="29" fill="white"/><circle r="26" fill="{color}"/>
    {symbols[state]}
  </g>
</svg>
'''


if __name__ == "__main__":
    for model in ("rapp-2", "biltema-giljotin"):
        for state in STATES:
            (IMAGES / f"snap-{model}-{state}.svg").write_text(render(model, state))
