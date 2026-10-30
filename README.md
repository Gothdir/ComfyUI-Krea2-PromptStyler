<img width="562" height="511" alt="image" src="https://github.com/user-attachments/assets/cc8c02cc-9709-4a69-b012-22e2425ae574" />




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

- **ca. 400 curated art styles** in 12 categories (Anime, Cartoon, Comics, Drawing, Design, Digital Painting, Painting, Cinematic Looks, Art Movements, 3D Render, Traditional Media, Dark & Horror)
- **Two-level style selection** – pick a category and the style dropdown dynamically filters to matching entries (no restart needed)
- **Full or short style text** – use the complete curated style description for maximum effect, or just a short "In the style of ..." sentence
- **Comprehensive camera settings** – 30 camera models (mirrorless, medium format, cinema, retro), 20 focal lengths, 12 apertures, 18 film stocks, 24 shot types, 26 lighting setups
- **Automatic depth of field hints** – selecting f/1.8 adds "shallow depth of field with creamy bokeh", f/11 adds "deep depth of field", etc.
- **Individual toggles per block** – art style, shot type, film stock and lighting can each be switched on/off; `use_camera` acts as a master switch that disables all technical camera segments at once
- **Wildcard mode** – randomizes all *activated* blocks per run (including the style category) without touching your dropdown selections; seed-based, so results are reproducible
- **Easily extendable** – all styles and camera options live in two JSON files, no code changes needed

## Two nodes

| Node | Style list | Selection |
|---|---|---|
| **Krea2 Prompt Styler** | `styles.json` (about 1250 styles) | Category > Medium > Family > Era > Style |
| **Krea2 Prompt Styler (Legacy)** | `artists.json` (about 400 styles) | Category > Style |

The legacy node is unchanged (same class name, so saved workflows still load). Both use `cameras.json`.

### Krea2 Prompt Styler (hierarchical)

Each dropdown only shows values that exist under the choices above it. Every level has `All` (Era: `Any`), so you can stop at any depth. `Era` narrows the style list by the sheet's era label (for example `Contemporary`, `Historical / Contemporary`). In wildcard mode the style is drawn at random from whatever the current Category / Medium / Family / Era selection allows.

Outputs of the new node: `prompt`, `settings`, `style_name`. The prompt is laid out as:

```
Style: <style name>: <style description>
Subject: <your text input>
<shot type, camera, film, lighting, if enabled>
```

`style_name` is the style actually used (the rolled one in wildcard mode), empty if `Artstyle` is off.

`styles.json` structure:

```json
{ "Category": { "Medium": { "Family": { "Style Name": { "era": "Contemporary", "text": "description" } } } } }
```

Rebuild it from a sheet export (TSV with the columns Order, Category, Medium, Family / Subcategory, Era / Period, Style Name, Wildcard Style, Original Row):

```bash
python tools/build_styles.py export.tsv styles.json report.md
```

Style names repeated in the sheet with different text are kept as `Name (v1)`, `Name (v2)`.

## Installation

### Manual

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Winter-unmuted/ComfyUI-Krea2-PromptStyler.git
```

Restart ComfyUI. If the style dropdown doesn't filter by category, hard-refresh your browser (Ctrl+Shift+R) to reload the frontend script.

## Usage

1. Add the node: **conditioning/krea2 → Krea2 Prompt Styler**
2. Connect a string source (e.g. a Primitive/Text node) to the `prompt` input (the new node: optional, the `Subject:` line is left out when nothing is connected)
3. Connect the `prompt` output to your CLIP Text Encode node
4. Optional: connect the `settings` output to a "Show Text" node to see exactly which values were used – especially handy in wildcard mode, where it shows the rolled values including the seed
5. Configure:

| Widget | Description |
|---|---|
| `Artstyle` | Toggle the art style block on/off |
| `Category` | Style category – filters the `style` dropdown live |
| `Style` | The actual art style, filtered by category |
| `full style text` | ON: full curated style description · OFF: short "In the style of ..." |
| `shot type` / `shot_type` | Framing and camera angle (close-up, wide shot, dutch angle, ...) |
| `camera` | **Master switch** – disables model, focal length, aperture *and* film stock |
| `camera model` / `focal length` / `aperture` | Technical camera settings |
| `film stock` / `film stock` | Analog film look (Portra, CineStill, Velvia, ...) |
| `lighting` / `lighting` | Lighting setup (golden hour, Rembrandt, neon, ...) |
| `wildcard` | Randomize all **activated** blocks – dropdown selections stay untouched |
| `seed` | Seed for wildcard mode – set to `randomize` for new combinations every run |

### Wildcard mode

<p align="center">
  <img src="https://github.com/user-attachments/assets/5813e0ad-2829-4b98-b78c-3267fb1fb2b2" width="50%">
  <img src="https://github.com/user-attachments/assets/8a139384-8c03-47f6-a400-164ea796f57a" width="50%">
  <img src="https://github.com/user-attachments/assets/c0430b16-7f14-418c-865a-648c2940d077" width="50%">
</p>


Turn on `wildcard` to let the node roll random values for every block that is currently activated: the style category, the art style within it, shot type, camera model, focal length, aperture, film stock and lighting. Blocks that are toggled off stay off. Your dropdown selections are never changed – turn the switch off and you're back to your exact configuration.

Thanks to a merge from winter-unmuted Wildcard now rotates through the selected Category. If you want to have it rotate through all Styles select the "All" Category.

The `seed` widget controls the randomness: leave it on `randomize` (default ComfyUI behavior via *control after generate*) to get a fresh combination on every queue, or set a fixed seed to reproduce a combination you liked.

Since the dropdowns keep showing your fixed selection, check the `settings` output to see which category, style and camera values were actually rolled.

**Tip:** Route the `prompt` output through a "Show Text" node to inspect the final prompt while fine-tuning.

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

Simply append values to any of the arrays: `models`, `focal lengths`, `apertures`, `film stocks`, `shot types`, `lighting`.

## Update log
03/08/26 Renaming the labels to make it less nerdy and added 5 new styles (in Cinematic)
26/07/26 Added native ComfyUI reload(R key) functionality so you wont have to restart comfyui when you change the artstyle etc jsons

## How it works

- `nodes_v2.py` loads `styles.json`; `/krea2_styler/styles_v2` serves the style rows to `web/js/krea2_styler_v2.js`, which runs the cascading dropdowns
- `nodes.py` (legacy) loads both JSON files at startup and builds the dropdowns
- A small API route (`/krea2_styler/artists`) serves the category→styles mapping to the frontend
- `web/js/krea2_styler.js` filters the style dropdown client-side whenever the category changes
- Saved workflows keep their style selection on load – the filter only resets the value if it doesn't belong to the selected category

## Credits
/u/Dear-Spend-2865 (reddit) for creating the masssive Wildcard list which was reformatted for this node.
