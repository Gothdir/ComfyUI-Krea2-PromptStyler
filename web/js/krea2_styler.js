import { app } from "../../scripts/app.js";

// Filtert das Style-Dropdown des Krea2 Prompt Styler nach gewaehlter Kategorie.
// Geaenderte JSON-Dateien werden serverseitig automatisch erkannt, ein
// "Refresh Node Definitions" (R) in ComfyUI reicht also nach dem Editieren.
app.registerExtension({
    name: "krea2.promptstyler.categoryfilter",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "Krea2PromptStyler") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            const node = this;

            const catWidget = node.widgets?.find((w) => w.name === "category");
            const styleWidget = node.widgets?.find((w) => w.name === "style");
            if (!catWidget || !styleWidget) return result;

            let mapping = null; // { Kategorie: [Stilnamen...] }

            function applyFilter(resetValue) {
                if (!mapping) return;
                const list = mapping[catWidget.value] || [];
                if (list.length === 0) return;
                styleWidget.options.values = list;
                // Wert nur zuruecksetzen, wenn er nicht zur Kategorie passt
                // (wichtig, damit geladene Workflows ihre Auswahl behalten)
                if (resetValue || !list.includes(styleWidget.value)) {
                    styleWidget.value = list[0];
                }
                node.setDirtyCanvas(true, true);
            }

            fetch("/krea2_styler/artists")
                .then((r) => r.json())
                .then((data) => {
                    mapping = data;
                    applyFilter(false);
                })
                .catch((e) =>
                    console.warn("[Krea2 Prompt Styler] Konnte Style-Liste nicht laden:", e)
                );

            const origCallback = catWidget.callback;
            catWidget.callback = function () {
                origCallback?.apply(this, arguments);
                applyFilter(true);
            };

            return result;
        };
    },
});
