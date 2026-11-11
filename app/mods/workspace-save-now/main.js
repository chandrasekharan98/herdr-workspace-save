// Saves the shown space straight away (ctrl-b shift-s): a key reaches a mod only through
// mod.open, so this tiny popup exists to run the save, then closes itself.

import { View, div } from "gpui-kit";
import { exec, run, props, focused, theme, notify, closeOverlay, appHome } from "herdr";

// Same as workspace-save/main.js: a mod can't import from another mod's folder.
async function saveSpace(space, andClose) {
  const r = await exec("python3", [`${appHome()}/mods/workspace-save/wss.py`, "app-save", space], { timeout: 120000 });
  if (r.code !== 0) {
    notify({ title: "Workspace not saved", body: r.stderr.trim(), level: "error" });
    return false;
  }
  const { label, path, warnings } = JSON.parse(r.stdout);
  notify({
    title: `Saved '${label}'`,
    body: [path, ...warnings].join("\n"),
    level: warnings.length ? "warning" : "success",
    timeout: warnings.length ? 15000 : 4000,
  });
  if (andClose) run("space.close", { id: space, confirmed: true });
  return true;
}

export default class WorkspaceSaveNow extends View {
  init(_props, cx) {
    const { overlay } = props() ?? {};
    const space = focused()?.space;
    if (!overlay) return; // `herdr-app check`: nothing to save
    cx.spawn(async () => {
      try { if (space) await saveSpace(space, false); } finally { closeOverlay(overlay); }
    });
  }

  render() {
    const t = theme();
    return div().size_full().p(12).text_size(13).text_color(t.muted).child("Saving workspace…");
  }
}
