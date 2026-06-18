/**
 * Foundation smoke-screen. Proves the design tokens, fonts, and Tailwind
 * pipeline are wired up. Replaced by the router + real pages in feat/dashboard.
 */
export default function App() {
  return (
    <main className="min-h-screen bg-page font-sans flex items-center justify-center">
      <div className="bg-card shadow-card rounded-card px-page-x py-page-y max-w-md text-center">
        <h1 className="text-2xl font-bold text-text-primary">linkHQ</h1>
        <p className="mt-2 text-sm text-text-muted">
          Foundation is live. Design tokens loaded.
        </p>
        <span className="mt-4 inline-block rounded-pill bg-primary px-4 py-1.5 text-sm font-semibold text-white">
          Ready to build
        </span>
      </div>
    </main>
  )
}
