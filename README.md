# ComfyUI Krea2 Prompt Styler

A prompt builder node for **Krea-2** and other **Flux-based models** in ComfyUI.

Takes your base prompt and wraps it in a natural language prompt with a selected art style and photographic camera settings – because Flux-based models respond far better to full sentences than to comma-separated tag lists.

**Output structure:**

```
[Art Style] [Your Prompt] [Shot Type] [Camera] [Film Stock] [Lighting]
```

**Example output:**

> In the style of Jim Lee. A lone samurai standing on a rainy rooftop overlooking a neon city. Low angle shot. Shot on a Sony A7 IV with a 55mm lens at f/1.8, shallow depth of field with creamy bokeh. CineStill 800T film look. Neon lighting.

## Features

- **300+ curated art styles** in 7 categories (Anime, Cartoon, Comics, Drawing, Design, Digital Painting, Painting)
- **Two-level style selection** – pick a category and the style dropdown dynamically filters to matching entries (no restart needed)
- **Full or short style text** – use the complete curated style description for maximum effect, or just a short "In the style of ..." sentence
- **Comprehensive camera settings** – 30 camera models (mirrorless, medium format, cinema, retro), 20 focal lengths, 12 apertures, 18 film stocks, 24 shot types, 26 lighting setups
- **Automatic depth of field hints** – selecting f/1.8 adds "shallow depth of field with creamy bokeh", f/11 adds "deep depth of field", etc.
- **Individual toggles per block** – art style, shot type, film stock and lighting can each be switched on/off; `use_camera` acts as a master switch that disables all technical camera segments at once
- **Easily extendable** – all styles and camera options live in two JSON files, no code changes needed

## Installation

### Manual

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Gothdir/ComfyUI-Krea2-PromptStyler.git
```

Restart ComfyUI. If the style dropdown doesn't filter by category, hard-refresh your browser (Ctrl+Shift+R) to reload the frontend script.

## Usage

1. Add the node: **conditioning/krea2 → Krea2 Prompt Styler**
2. Connect a string source (e.g. a Primitive/Text node) to the `prompt` input
3. Connect the `prompt` output to your CLIP Text Encode node
4. Configure:

| Widget | Description |
|---|---|
| `use_artstyle` | Toggle the art style block on/off |
| `category` | Style category – filters the `style` dropdown live |
| `style` | The actual art style, filtered by category |
| `full_style_text` | ON: full curated style description · OFF: short "In the style of ..." |
| `use_shot_type` / `shot_type` | Framing and camera angle (close-up, wide shot, dutch angle, ...) |
| `use_camera` | **Master switch** – disables model, focal length, aperture *and* film stock |
| `camera_model` / `focal_length` / `aperture` | Technical camera settings |
| `use_film_stock` / `film_stock` | Analog film look (Portra, CineStill, Velvia, ...) |
| `use_lighting` / `lighting` | Lighting setup (golden hour, Rembrandt, neon, ...) |

**Tip:** Route the output through a "Show Text" node to inspect the final prompt while fine-tuning.

**Note:** ComfyUI cannot grey out widgets dynamically – when a toggle is off, its dropdowns stay visible but are simply ignored.

## Extending the lists

Both lists are plain JSON files inside the node folder. Edit them and restart ComfyUI.

### `artists.json`

```json
{
  "Category Name": {
    "Style Name": "Full style description used when full_style_text is ON",
    "Another Style": ""
  }
}
```

- New categories automatically appear in the `category` dropdown
- An empty description is fine – the node then falls back to the short "In the style of ..." sentence
- Style names must be unique across **all** categories

### `cameras.json`

Simply append values to any of the arrays: `models`, `focal_lengths`, `apertures`, `film_stocks`, `shot_types`, `lighting`.

## How it works

- `nodes.py` loads both JSON files at startup and builds the dropdowns
- A small API route (`/krea2_styler/artists`) serves the category→styles mapping to the frontend
- `web/js/krea2_styler.js` filters the style dropdown client-side whenever the category changes
- Saved workflows keep their style selection on load – the filter only resets the value if it doesn't belong to the selected category

## Honorable Metnion
Reddit user
/u/Dear-Spend-2865
for creating a massive Wildcard list which I took and reformatted for this node.
