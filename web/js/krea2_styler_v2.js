import { app } from "../../scripts/app.js";

// Cascading filter for the hierarchical Krea2 Prompt Styler:
//   Category > Medium > Family > Era > Style
// Each dropdown shows only values that exist under the choices above it.
// Data comes from /krea2_styler/styles_v2 as rows [cat, med, fam, era, name].
// Loaded workflows keep their saved values as long as those are still valid.
const ALL = "All";
const ANY = "Any";

app.registerExtension({
    name: "krea2.promptstyler.cascade",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Krea2PromptStylerV2") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            const node = this;

            const w = {
                cat: node.widgets?.find((x) => x.name === "Category"),
                med: node.widgets?.find((x) => x.name === "Medium"),
                fam: node.widgets?.find((x) => x.name === "Family"),
                era: node.widgets?.find((x) => x.name === "Era"),
                style: node.widgets?.find((x) => x.name === "Style"),
            };
            if (!w.cat || !w.med || !w.fam || !w.era || !w.style) return result;

            let rows = null; // [[cat, med, fam, era, name], ...]

            const uniq = (list) => [...new Set(list)];
            const sortCI = (list) => list.slice().sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));

            // rows that match the selections of the levels above `level`
            // level: 0 cat, 1 med, 2 fam, 3 era, 4 style
            function scope(level) {
                const c = w.cat.value, m = w.med.value, f = w.fam.value, e = w.era.value;
                return rows.filter((r) =>
                    (level <= 0 || c === ALL || r[0] === c) &&
                    (level <= 1 || m === ALL || r[1] === m) &&
                    (level <= 2 || f === ALL || r[2] === f) &&
                    (level <= 3 || e === ANY || r[3] === e)
                );
            }

            // Set a widget's option list; fall back to the "all" entry if the value is no longer valid.
            function setOptions(widget, values, allLabel, forceReset) {
                widget.options.values = values;
                if (forceReset || !values.includes(widget.value)) {
                    widget.value = allLabel;
                }
            }

            // Recompute everything below `fromLevel` (0 = all dropdowns).
            // forceReset: a user just changed a higher level, so lower ones go back to All/Any.
            function refresh(fromLevel, forceReset) {
                if (!rows) return;

                if (fromLevel <= 0) {
                    setOptions(w.cat, [ALL, ...uniq(rows.map((r) => r[0]))], ALL, false);
                }
                if (fromLevel <= 1) {
                    const s = scope(1);
                    setOptions(w.med, [ALL, ...uniq(s.map((r) => r[1]))], ALL, forceReset);
                }
                if (fromLevel <= 2) {
                    const s = scope(2);
                    setOptions(w.fam, [ALL, ...sortCI(uniq(s.map((r) => r[2])))], ALL, forceReset);
                }
                if (fromLevel <= 3) {
                    const s = scope(3);
                    const counts = new Map();
                    s.forEach((r) => r[3] && counts.set(r[3], (counts.get(r[3]) || 0) + 1));
                    const eras = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || a.localeCompare(b));
                    setOptions(w.era, [ANY, ...eras], ANY, forceReset);
                }
                if (fromLevel <= 4) {
                    const names = sortCI(scope(4).map((r) => r[4]));
                    if (names.length) {
                        w.style.options.values = names;
                        if (forceReset || !names.includes(w.style.value)) {
                            w.style.value = names[0];
                        }
                    }
                }
                node.setDirtyCanvas(true, true);
            }

            // changing a level refreshes the levels below it
            const hook = (widget, level) => {
                const orig = widget.callback;
                widget.callback = function () {
                    orig?.apply(this, arguments);
                    refresh(level + 1, true);
                };
            };
            hook(w.cat, 0);
            hook(w.med, 1);
            hook(w.fam, 2);
            hook(w.era, 3);

            fetch("/krea2_styler/styles_v2")
                .then((r) => r.json())
                .then((data) => {
                    rows = data.records;
                    refresh(0, false);
                })
                .catch((e) =>
                    console.warn("[Krea2 Prompt Styler] Could not load style list:", e)
                );

            return result;
        };
    },
});
