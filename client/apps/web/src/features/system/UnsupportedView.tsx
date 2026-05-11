/**
 * Mobile / unsupported viewport gate. Per docs/40-features/WEB-APP.md §10.3 —
 * the app is desktop-first. Auth pages and share page remain responsive; this
 * view is shown for workspace-class routes on small viewports.
 */
export function UnsupportedView() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center gap-6 px-6 py-12 text-center">
      <span className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
        Optimized for desktop
      </span>
      <h1 className="max-w-md text-2xl font-semibold text-fg">
        Workspace inspection works best on a wider screen
      </h1>
      <p className="max-w-md text-sm text-fg-muted">
        Tables, charts, and the agent saga need horizontal real estate. Email yourself a
        link to open Baseflo on a desktop browser.
      </p>
      <p className="text-xs text-fg-subtle">
        Open this page on a desktop browser to continue.
      </p>
    </div>
  );
}
