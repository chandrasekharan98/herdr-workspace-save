// Saved workspaces: search, reopen, delete (ctrl+x, undo ctrl+z), save this space, save and close.
// wss.py beside this file does the work (the herdr TUI plugin runs the same file), so saves
// from either one show up in both.

import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input, ScrollHandle } from "gpui-base";
import { exec, run, props, focused, theme, notify, closeOverlay, appHome } from "herdr";

const wss = (...args) =>
  exec("python3", [`${appHome()}/mods/workspace-save/wss.py`, ...args], { timeout: 120000 });

// Same as workspace-save-now/main.js: a mod can't import from another mod's folder.
async function saveSpace(space, andClose) {
  const r = await wss("app-save", space);
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

export default class WorkspaceSave extends View {
  init(_props, cx) {
    this.saves = [];
    this.filter = "";
    this.at = 0;
    this.busy = null; // what's running, shown instead of the list
    this.note = "";
    this.scroll = ScrollHandle.new();
    this.input = InputState.new({ placeholder: "Search saved workspaces…" });
    this.input.on("change", (_e, cx) => { this.filter = this.input.value(); this.at = 0; cx.notify(); });
    this.input.on("submit", (_e, cx) => this.open(cx));
    this.input.focus();
    cx.timer.after(600, () => this.input.focus());
    this.reload(cx);
  }

  reload(cx) {
    cx.spawn(async (cx) => {
      const r = await wss("app-list");
      if (r.code === 0) this.saves = JSON.parse(r.stdout);
      else this.note = r.stderr.trim();
      this.saves.sort((a, b) => b.saved_at.localeCompare(a.saved_at));
      cx.notify();
    });
  }

  rows() {
    const f = this.filter.toLowerCase();
    return this.saves.filter((s) => !f || `${s.label} ${s.name}`.toLowerCase().includes(f));
  }

  close() {
    if (props()?.overlay) closeOverlay(props().overlay);
  }

  // Runs one wss.py job with the dialog open: closing it would cancel the job.
  job(cx, label, work) {
    this.busy = label;
    cx.notify();
    cx.spawn(async (cx) => {
      try { await work(cx); } finally { this.busy = null; cx.notify(); }
    });
  }

  open(cx) {
    const s = this.rows()[this.at];
    if (!s || this.busy) return;
    this.job(cx, `Reopening '${s.label}'…`, async () => {
      const r = await wss("app-restore", s.name);
      if (r.code !== 0) {
        notify({ title: `Couldn't reopen '${s.label}'`, body: r.stderr.trim(), level: "error" });
        return;
      }
      const { warnings } = JSON.parse(r.stdout);
      notify({
        title: `Reopened '${s.label}'`,
        body: warnings.join("\n") || undefined,
        level: warnings.length ? "warning" : "success",
        timeout: warnings.length ? 15000 : 4000,
      });
      this.close();
    });
  }

  save(cx, andClose) {
    const space = focused()?.space;
    if (!space || this.busy) return;
    this.job(cx, andClose ? "Saving and closing…" : "Saving…", async (cx) => {
      if (!(await saveSpace(space, andClose))) return;
      if (andClose) return this.close();
      this.reload(cx);
    });
  }

  remove(cx, s) {
    if (!s || this.busy) return;
    this.job(cx, null, async (cx) => {
      await wss("delete", s.name);
      this.note = `Deleted '${s.label}' · ctrl+z undoes · kept 7 days in trash/`;
      this.reload(cx);
    });
  }

  undo(cx) {
    this.job(cx, null, async (cx) => {
      await wss("undelete");
      this.note = "";
      this.reload(cx);
    });
  }

  render(cx) {
    const t = theme();
    const rows = this.rows();
    this.at = Math.max(0, Math.min(this.at, rows.length - 1));
    const button = (id, label, onClick) =>
      div().id(id).px(10).py(5).rounded(6).text_size(12).border_1().border_color(t.border)
        .text_color(t.foreground).cursor_pointer().hover((s) => s.bg(t.hover))
        .on_click((_e, cx) => onClick(cx)).child(label);

    return v_flex().id("ws-root").size_full().p(18).gap(10).bg(t.popover).text_size(13)
      .on_key_down((e, cx) => {
        const k = e.key, ctrl = e.modifiers.control;
        if (k === "escape") return this.close();
        if (k === "down") this.at = Math.min(this.at + 1, rows.length - 1);
        else if (k === "up") this.at = Math.max(this.at - 1, 0);
        else if (ctrl && k === "x") this.remove(cx, rows[this.at]);
        else if (ctrl && k === "z") this.undo(cx);
        else if (ctrl && k === "s") this.save(cx, e.modifiers.shift);
        else return;
        this.scroll.scroll_to_item(this.at);
        cx.stop_propagation();
        cx.notify();
      })
      .child(h_flex().items_center().gap(8)
        .child(div().flex_1().text_size(15).font_semibold().text_color(t.foreground).child("Saved workspaces"))
        .child(button("ws-save", "Save this space", (cx) => this.save(cx, false)))
        .child(button("ws-save-close", "Save and close", (cx) => this.save(cx, true))))
      .child(h_flex().h(36).flex_none().px(10).items_center().rounded(9).border_1().border_color(t.accent).bg(t.background)
        .child(Input.new(this.input).flex_1().h_full().text_size(12.8).text_color(t.foreground)))
      .child(this.busy
        ? div().flex_1().text_color(t.muted).child(this.busy)
        : v_flex().id("ws-list").flex_1().min_h(0).overflow_y_scrollbar().track_scroll(this.scroll).children(
          rows.length ? rows.map((s, i) =>
            h_flex().id(`ws-${s.name}`).px(10).py(7).gap(10).rounded(6).items_center().cursor_pointer()
              .bg(i === this.at ? t.selected : t.popover).hover((st) => st.bg(i === this.at ? t.selected : t.hover))
              .on_click((_e, cx) => { this.at = i; this.open(cx); })
              .child(div().flex_1().truncate().text_color(t.foreground).child(s.label))
              .child(div().text_color(t.dim).text_size(12).child(`${s.tabs} tab${s.tabs === 1 ? "" : "s"}`))
              .child(div().text_color(t.dim).text_size(12).child(s.saved_at.replace("T", " ").slice(0, 16)))
              .child(div().id(`ws-del-${s.name}`).px(6).rounded(4).text_color(t.dim).hover((st) => st.text_color(t.blocked))
                .on_click((_e, cx) => { cx.stop_propagation(); this.remove(cx, s); }).child("✕")))
            : [div().p(10).text_color(t.muted).child(this.saves.length ? "No match." : "No saved workspaces yet.")]))
      .child(div().text_size(11).text_color(t.dim).child(this.note ||
        "Enter reopens · ctrl+x deletes · ctrl+z undoes · ctrl+s saves this space · ctrl+shift+s saves and closes · Esc"));
  }
}
