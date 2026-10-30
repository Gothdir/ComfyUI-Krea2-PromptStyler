"""
Krea2 Prompt Styler (hierarchical)
----------------------------------
Same prompt layout as the legacy node, but the style list comes from
styles.json and is chosen through a cascade:

    Category > Medium > Family > Era > Style

Every level has an "All" option (Era: "Any"). The JS frontend
(web/js/krea2_styler_v2.js) narrows each dropdown to what is valid for the
choices above it. All values stay in the widget lists so that ComfyUI's
server-side validation accepts them.

styles.json structure:
    { Category: { Medium: { Family: { Style Name: {"era": str, "text": str} } } } }
Rebuild it from a sheet export with tools/build_styles.py.

The legacy node (nodes.py + artists.json) is not touched. Camera lists are
shared with it (cameras.json).
"""

import json
import os
import random
import re

from . import nodes as _legacy

NODE_DIR = os.path.dirname(os.path.abspath(__file__))
STYLES_FILE = "styles.json"

ALL = "All"
ANY = "Any"

_FALLBACK_STYLES = {"Fallback": {"Fallback": {"Fallback": {"No styles loaded": {"era": "General", "text": ""}}}}}

_MTIME = None

# Flat records: dict(cat, med, fam, era, name, text)
RECORDS = []
LOOKUP = {}            # style name -> record
CATEGORY_CHOICES = [ALL]
MEDIUM_CHOICES = [ALL]
FAMILY_CHOICES = [ALL]
ERA_CHOICES = [ANY]
ALL_STYLE_NAMES = []
_DEFAULT_STYLE = ""


def _load_styles():
    path = os.path.join(NODE_DIR, STYLES_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Krea2 Prompt Styler] Could not load {STYLES_FILE}: {e}")
        return _FALLBACK_STYLES


def _styles_changed():
    global _MTIME
    try:
        mt = os.path.getmtime(os.path.join(NODE_DIR, STYLES_FILE))
    except OSError:
        mt = 0
    if mt != _MTIME:
        _MTIME = mt
        return True
    return False


def reload_styles(force=False):
    """(Re)build all lists from styles.json. Without force, only if the file changed."""
    global RECORDS, LOOKUP, CATEGORY_CHOICES, MEDIUM_CHOICES, FAMILY_CHOICES
    global ERA_CHOICES, ALL_STYLE_NAMES, _DEFAULT_STYLE

    if not force and not _styles_changed() and RECORDS:
        return False

    tree = _load_styles()
    records = []
    for cat, mediums in tree.items():
        for med, families in mediums.items():
            for fam, styles in families.items():
                for name, entry in styles.items():
                    if isinstance(entry, str):          # tolerate plain "name: text"
                        entry = {"era": "", "text": entry}
                    # Same "/" handling as the legacy node (rgthree treats "/" as a folder separator)
                    records.append({
                        "cat": cat, "med": med, "fam": fam,
                        "era": entry.get("era", "") or "",
                        "name": name.replace("/", "∕"),
                        "text": entry.get("text", "") or "",
                    })

    RECORDS = records
    LOOKUP = {r["name"]: r for r in records}

    def uniq(key, sort=False):
        seen = []
        for r in records:
            if r[key] and r[key] not in seen:
                seen.append(r[key])
        return sorted(seen, key=str.lower) if sort else seen

    CATEGORY_CHOICES = [ALL] + uniq("cat")
    MEDIUM_CHOICES = [ALL] + uniq("med")
    FAMILY_CHOICES = [ALL] + uniq("fam", sort=True)
    # Era values in order of how many styles use them (most common first)
    counts = {}
    for r in records:
        if r["era"]:
            counts[r["era"]] = counts.get(r["era"], 0) + 1
    ERA_CHOICES = [ANY] + sorted(counts, key=lambda e: (-counts[e], e))
    ALL_STYLE_NAMES = sorted(LOOKUP, key=str.lower)
    _DEFAULT_STYLE = ALL_STYLE_NAMES[0] if ALL_STYLE_NAMES else ""
    return True


def _pool(category, medium, family, era):
    """Style names matching the current selection ('All'/'Any' = no constraint)."""
    out = []
    for r in RECORDS:
        if category != ALL and r["cat"] != category:
            continue
        if medium != ALL and r["med"] != medium:
            continue
        if family != ALL and r["fam"] != family:
            continue
        if era != ANY and r["era"] != era:
            continue
        out.append(r["name"])
    return sorted(out, key=str.lower)


def _payload():
    return {"records": [[r["cat"], r["med"], r["fam"], r["era"], r["name"]] for r in RECORDS]}


reload_styles(force=True)


# ---------------------------------------------------------------------------
# API route for the frontend
# ---------------------------------------------------------------------------

try:
    from server import PromptServer
    from aiohttp import web

    _ROUTE_PATH = "/krea2_styler/styles_v2"

    def _route_exists(routes, path):
        try:
            return any(getattr(r, "path", None) == path for r in routes)
        except Exception:
            return False

    if not _route_exists(PromptServer.instance.routes, _ROUTE_PATH):

        @PromptServer.instance.routes.get(_ROUTE_PATH)
        async def _krea2_get_styles_v2(request):
            reload_styles()
            return web.json_response(_payload())
    else:
        print("[Krea2 Prompt Styler] Route already registered - the node folder is "
              "probably in custom_nodes twice. Please remove the duplicate.")
except Exception:
    # Outside ComfyUI (tests): ignore
    pass


class Krea2PromptStylerV2:
    CATEGORY = "conditioning/krea2"
    FUNCTION = "build_prompt"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "settings", "style_name")

    @classmethod
    def INPUT_TYPES(cls):
        reload_styles()
        _legacy.reload_lists()      # keeps cameras.json fresh
        cam = _legacy.CAMERAS
        return {
            "required": {
                # ------ Artstyle ------
                "Artstyle": ("BOOLEAN", {"default": True}),
                "Category": (CATEGORY_CHOICES, {"default": ALL}),
                "Medium": (MEDIUM_CHOICES, {"default": ALL}),
                "Family": (FAMILY_CHOICES, {"default": ALL}),
                "Era": (ERA_CHOICES, {"default": ANY}),
                # Holds ALL styles (needed for validation); the frontend narrows the display.
                "Style": (ALL_STYLE_NAMES, {"default": _DEFAULT_STYLE}),
                "Full Style Text": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "ON: use the full style description from styles.json. "
                               "OFF: only a short 'In the style of ...' sentence."
                }),

                # ------ Shot / Framing ------
                "Framing": ("BOOLEAN", {"default": False}),
                "Shot Type": (cam["shot_types"],),

                # ------ Camera (master switch) ------
                "Camera": ("BOOLEAN", {"default": False}),
                "Camera Model": (cam["models"],),
                "Focal Length": (cam["focal_lengths"], {"default": "50mm"}),
                "Aperture": (cam["apertures"], {"default": "f/1.8"}),
                "Film Look": ("BOOLEAN", {"default": False}),
                "Film Stock": (cam["film_stocks"],),

                # ------ Lighting ------
                "Lighting": ("BOOLEAN", {"default": False}),
                "Light Setup": (cam["lighting"],),

                # ------ Wildcard mode ------
                "Wildcard": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Rolls random values for every ENABLED block without changing the "
                               "dropdowns. The style is drawn from the current Category / Medium / "
                               "Family / Era selection ('All' / 'Any' = no limit at that level)."
                }),
                "Seed": ("INT", {
                    "default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                    "control_after_generate": True,
                    "tooltip": "Seed for wildcard mode. 'randomize' gives new combinations every "
                               "run, a fixed value makes them reproducible."
                }),
            },
            "optional": {
                # Optional link: if nothing is connected (or the text is empty),
                # the "Subject:" line is left out of the prompt.
                "prompt": ("STRING", {"forceInput": True}),
            },
        }

    def build_prompt(self, **kwargs):
        cam = _legacy.CAMERAS
        prompt = kwargs.get("prompt", "")
        use_artstyle = kwargs.get("Artstyle", True)
        category = kwargs.get("Category", ALL)
        medium = kwargs.get("Medium", ALL)
        family = kwargs.get("Family", ALL)
        era = kwargs.get("Era", ANY)
        style = kwargs.get("Style", _DEFAULT_STYLE)
        full_style_text = kwargs.get("Full Style Text", True)
        use_shot_type = kwargs.get("Framing", False)
        shot_type = kwargs.get("Shot Type", "")
        use_camera = kwargs.get("Camera", True)
        camera_model = kwargs.get("Camera Model", "")
        focal_length = kwargs.get("Focal Length", "")
        aperture = kwargs.get("Aperture", "")
        use_film_stock = kwargs.get("Film Look", False)
        film_stock = kwargs.get("Film Stock", "")
        use_lighting = kwargs.get("Lighting", False)
        lighting = kwargs.get("Light Setup", "")
        use_wildcard = kwargs.get("Wildcard", False)
        seed = kwargs.get("Seed", 0)

        # ------ Wildcard mode ------
        if use_wildcard:
            rng = random.Random(seed)
            if use_artstyle:
                pool = _pool(category, medium, family, era)
                if pool:
                    style = rng.choice(pool)
            if use_shot_type:
                shot_type = rng.choice(cam["shot_types"])
            if use_camera:
                camera_model = rng.choice(cam["models"])
                focal_length = rng.choice(cam["focal_lengths"])
                aperture = rng.choice(cam["apertures"])
                if use_film_stock:
                    film_stock = rng.choice(cam["film_stocks"])
            if use_lighting:
                lighting = rng.choice(cam["lighting"])

        lines = []
        style_name = ""

        # ------ Line 1: Style ------
        rec = LOOKUP.get(style)
        if use_artstyle and rec:
            style_name = style
            if full_style_text and rec["text"]:
                lines.append(f"Style: {style}: {rec['text']}")
            else:
                clean = style.replace(" Style", "").replace(" (Generic)", "")
                clean = re.sub(r" \(v\d+\)$", "", clean)     # drop (v1)/(v2) test suffix
                lines.append(f"Style: In the style of {clean}.")

        # ------ Line 2: Subject (the text input) ------
        base = (prompt or "").strip()
        if base:
            if not base.endswith((".", "!", "?")):
                base += "."
            lines.append(f"Subject: {base}")

        # ------ Line 3: shot type, camera, film, lighting (one line, only if enabled) ------
        tech = []
        if use_shot_type:
            tech.append(f"{shot_type.capitalize()}.")
        if use_camera:
            c = f"Shot on a {camera_model} with a {focal_length} lens at {aperture}"
            c += _legacy._dof_hint(aperture)
            tech.append(c + ".")
            if use_film_stock:
                tech.append(f"{film_stock} film look.")
        if use_lighting:
            tech.append(f"{lighting.capitalize()}.")
        if tech:
            lines.append(" ".join(tech))

        # ------ settings output ------
        info = []
        if use_wildcard:
            info.append(f"Wildcard: ON (seed {seed})")
        if use_artstyle and rec:
            mode = "full text" if full_style_text else "short"
            info.append(f"Style: {rec['cat']} > {rec['med']} > {rec['fam']} > {style} ({mode})")
            if rec["era"]:
                info.append(f"Era: {rec['era']}")
        else:
            info.append("Style: off")
        info.append(f"Shot type: {shot_type}" if use_shot_type else "Shot type: off")
        if use_camera:
            info.append(f"Camera: {camera_model}, {focal_length}, {aperture}")
            info.append(f"Film stock: {film_stock}" if use_film_stock else "Film stock: off")
        else:
            info.append("Camera: off")
        info.append(f"Lighting: {lighting}" if use_lighting else "Lighting: off")

        return ("\n".join(lines), "\n".join(info), style_name)


NODE_CLASS_MAPPINGS = {
    "Krea2PromptStylerV2": Krea2PromptStylerV2,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2PromptStylerV2": "Krea2 Prompt Styler",
}
