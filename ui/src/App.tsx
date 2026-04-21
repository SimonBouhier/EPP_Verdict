import { Link, Route, Routes } from 'react-router-dom';
import ClaimViewerPage from '@/routes/claim-viewer';
import HomePage from '@/routes/home';

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground antialiased">
      <header className="border-b border-border">
        <div className="mx-auto flex h-14 max-w-5xl items-center px-4">
          <Link to="/" className="font-mono text-sm font-semibold tracking-tight">
            EPP
          </Link>
          <nav className="ml-auto flex items-center gap-4 text-sm">
            <Link
              to="/"
              className="text-muted-foreground transition-colors hover:text-foreground"
            >
              Runs
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/claims" element={<ClaimViewerPage />} />
          <Route
            path="*"
            element={
              <p className="text-sm text-muted-foreground">
                404 —{' '}
                <Link to="/" className="underline underline-offset-2">
                  back home
                </Link>
              </p>
            }
          />
        </Routes>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-4 text-xs text-muted-foreground">
          <span className="font-mono">EPP v0.1 · MIT</span>
          <span className="font-mono">benchmark_runs/</span>
        </div>
      </footer>
    </div>
  );
}
