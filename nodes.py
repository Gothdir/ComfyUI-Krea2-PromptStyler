"""
Krea2 Prompt Styler
-------------------
Baut aus einem Basis-Prompt, einem Artstyle und Kamera-Einstellungen
einen fertigen Prompt in natuerlicher Sprache fuer Krea-2 / Flux-basierte Modelle.

Aufbau des Ergebnisses:
    [Style-Text]  [Basis-Prompt]  [Shot Type]  [Kamera]  [Film Stock]  [Lighting]

Die Auswahl-Listen kommen aus artists.json und cameras.json im Node-Ordner
und koennen dort beliebig erweitert werden (ComfyUI danach neu starten).

Das Style-Dropdown wird per JS-Frontend (web/js/krea2_styler.js) dynamisch
nach der gewaehlten Kategorie gefiltert.
"""

import json
import os
import random

NODE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_json(filename, fallback):
    path = os.path.join(NODE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Krea2 Prompt Styler] Konnte {filename} nicht laden: {e}")
        return fallback


# ---------------------------------------------------------------------------
# JSONs laden (einmal beim Start von ComfyUI)
# ---------------------------------------------------------------------------

ARTISTS = _load_json("artists.json", {"Fallback": {"No styles loaded": ""}})
CAMERAS = _load_json("cameras.json", {
    "models": ["Sony A7 IV"],
    "focal_lengths": ["50mm"],
    "apertures": ["f/1.8"],
    "film_stocks": ["Kodak Portra 400"],
    "shot_types": ["medium shot"],
    "lighting": ["soft studio lighting"],
})

_REAL_CATEGORIES = list(ARTISTS.keys())
CATEGORY_CHOICES = ["All"] + _REAL_CATEGORIES

# Stilname -> Beschreibung (Namen sind kategorieuebergreifend eindeutig)
STYLE_LOOKUP = {}
ALL_STYLE_NAMES = []
for _cat in _REAL_CATEGORIES:
    for _name in sorted(ARTISTS[_cat].keys()):
        STYLE_LOOKUP[_name] = ARTISTS[_cat][_name]
        ALL_STYLE_NAMES.append(_name)
ALL_STYLE_NAMES = sorted(ALL_STYLE_NAMES)


def _styles_for_category(cat):
    """Style-Pool fuer eine Kategorie. 'All' (oder eine unbekannte Kategorie)
    liefert die komplette, ungefilterte Liste."""
    if cat == "All" or cat not in ARTISTS:
        return ALL_STYLE_NAMES
    return sorted(ARTISTS[cat].keys())


_DEFAULT_CAT = "All"
_DEFAULT_STYLE = ALL_STYLE_NAMES[0] if ALL_STYLE_NAMES else ""


# ---------------------------------------------------------------------------
# API-Route: liefert dem JS-Frontend die Kategorie->Styles-Zuordnung
# ---------------------------------------------------------------------------

try:
    from server import PromptServer
    from aiohttp import web

    @PromptServer.instance.routes.get("/krea2_styler/artists")
    async def _krea2_get_artists(request):
        mapping = {cat: sorted(entries.keys()) for cat, entries in ARTISTS.items()}
        mapping["All"] = ALL_STYLE_NAMES
        return web.json_response(mapping)
except Exception:
    # Ausserhalb von ComfyUI (z. B. beim Testen) einfach ignorieren
    pass


def _dof_hint(aperture: str) -> str:
    """Passenden Depth-of-Field-Zusatz zur Blende liefern."""
    try:
        f_num = float(aperture.replace("f/", "").replace(",", "."))
    except ValueError:
        return ""
    if f_num <= 2.0:
        return ", shallow depth of field with creamy bokeh"
    if f_num <= 4.0:
        return ", moderately shallow depth of field"
    if f_num >= 8.0:
        return ", deep depth of field with everything in sharp focus"
    return ""


class Krea2PromptStyler:
    CATEGORY = "conditioning/krea2"
    FUNCTION = "build_prompt"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "settings")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"forceInput": True}),

                # ------ Artstyle ------
                "use_artstyle": ("BOOLEAN", {"default": True}),
                "category": (CATEGORY_CHOICES, {"default": _DEFAULT_CAT}),
                # Enthaelt ALLE Styles (noetig fuer die Validierung);
                # das JS-Frontend filtert die Anzeige nach Kategorie.
                "style": (ALL_STYLE_NAMES, {"default": _DEFAULT_STYLE}),
                "full_style_text": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "AN: komplette Stilbeschreibung aus artists.json verwenden. "
                               "AUS: nur kurzer Satz 'In the style of ...'."
                }),

                # ------ Shot / Framing ------
                "use_shot_type": ("BOOLEAN", {"default": False}),
                "shot_type": (CAMERAS["shot_types"],),

                # ------ Kamera (Master-Switch) ------
                "use_camera": ("BOOLEAN", {"default": True}),
                "camera_model": (CAMERAS["models"],),
                "focal_length": (CAMERAS["focal_lengths"], {"default": "50mm"}),
                "aperture": (CAMERAS["apertures"], {"default": "f/1.8"}),
                "use_film_stock": ("BOOLEAN", {"default": False}),
                "film_stock": (CAMERAS["film_stocks"],),

                # ------ Lighting ------
                "use_lighting": ("BOOLEAN", {"default": False}),
                "lighting": (CAMERAS["lighting"],),

                # ------ Wildcard-Modus ------
                "use_wildcard": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Wuerfelt fuer alle AKTIVIERTEN Bloecke zufaellige Werte, "
                               "ohne die Auswahl in den Dropdowns zu veraendern. "
                               "Die gewaehlte Kategorie wird respektiert (bei 'All' wird "
                               "aus allen Styles gewuerfelt), nur der Style innerhalb "
                               "dieser Kategorie wird gewuerfelt."
                }),
                "seed": ("INT", {
                    "default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF,
                    "control_after_generate": True,
                    "tooltip": "Seed fuer den Wildcard-Modus. 'randomize' sorgt fuer neue "
                               "Kombinationen bei jedem Run, fester Wert macht sie reproduzierbar."
                }),
            }
        }

    def build_prompt(self, prompt, use_artstyle, category, style, full_style_text,
                     use_shot_type, shot_type,
                     use_camera, camera_model, focal_length, aperture,
                     use_film_stock, film_stock,
                     use_lighting, lighting,
                     use_wildcard, seed):

        # ------ Wildcard-Modus: aktivierte Bloecke zufaellig wuerfeln ------
        # Die Dropdown-Auswahl im Node bleibt unveraendert, nur die hier
        # verwendeten Werte werden ersetzt. Nicht aktivierte Bloecke bleiben aus.
        if use_wildcard:
            rng = random.Random(seed)
            if use_artstyle:
                pool = _styles_for_category(category)
                if pool:
                    style = rng.choice(pool)
            if use_shot_type:
                shot_type = rng.choice(CAMERAS["shot_types"])
            if use_camera:
                camera_model = rng.choice(CAMERAS["models"])
                focal_length = rng.choice(CAMERAS["focal_lengths"])
                aperture = rng.choice(CAMERAS["apertures"])
                if use_film_stock:
                    film_stock = rng.choice(CAMERAS["film_stocks"])
            if use_lighting:
                lighting = rng.choice(CAMERAS["lighting"])

        parts = []

        # ------ 1. Artstyle (vorne) ------
        if use_artstyle and style in STYLE_LOOKUP:
            desc = STYLE_LOOKUP[style]
            if full_style_text and desc:
                # Komplette Wildcard-Beschreibung als eigener Satzblock
                parts.append(f"{style}: {desc}")
            else:
                clean = style.replace(" Style", "").replace(" (Generic)", "")
                parts.append(f"In the style of {clean}.")

        # ------ 2. Basis-Prompt ------
        base = (prompt or "").strip()
        if base:
            if not base.endswith((".", "!", "?")):
                base += "."
            parts.append(base)

        # ------ 3. Shot Type ------
        if use_shot_type:
            parts.append(f"{shot_type.capitalize()}.")

        # ------ 4. Kamera (Master-Switch deaktiviert ALLES Technische) ------
        if use_camera:
            cam = f"Shot on a {camera_model} with a {focal_length} lens at {aperture}"
            cam += _dof_hint(aperture)
            parts.append(cam + ".")
            if use_film_stock:
                parts.append(f"{film_stock} film look.")

        # ------ 5. Lighting ------
        if use_lighting:
            parts.append(f"{lighting.capitalize()}.")

        # ------ Settings-Uebersicht fuer den zweiten Output ------
        # Zeigt die tatsaechlich verwendeten Werte (im Wildcard-Modus also
        # die gewuerfelten) - ideal fuer einen "Show Text"-Node.
        info = []
        if use_wildcard:
            info.append(f"Wildcard: ON (seed {seed})")
        if use_artstyle and style in STYLE_LOOKUP:
            mode = "full text" if full_style_text else "short"
            info.append(f"Style: {category} / {style} ({mode})")
        else:
            info.append("Style: off")
        info.append(f"Shot type: {shot_type}" if use_shot_type else "Shot type: off")
        if use_camera:
            info.append(f"Camera: {camera_model}, {focal_length}, {aperture}")
            info.append(f"Film stock: {film_stock}" if use_film_stock else "Film stock: off")
        else:
            info.append("Camera: off")
        info.append(f"Lighting: {lighting}" if use_lighting else "Lighting: off")
        settings = "\n".join(info)

        final_prompt = " ".join(parts)
        return (final_prompt, settings)


NODE_CLASS_MAPPINGS = {
    "Krea2PromptStyler": Krea2PromptStyler,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Krea2PromptStyler": "Krea2 Prompt Styler",
}
