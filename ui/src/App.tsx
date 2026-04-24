import { Link, NavLink, Route, Routes } from 'react-router-dom';
import ClaimViewerPage from '@/routes/claim-viewer';
import FlywheelPage from '@/routes/flywheel';
import HomePage from '@/routes/home';
import OnChainPage from '@/routes/onchain';

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground antialiased">
      <header className="border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center px-4">
          <Link to="/" className="flex items-center gap-2">
            <span aria-hidden="true" className="block size-2 rounded-full bg-cyan shadow-[0_0_12px_var(--color-cyan)]" />
            <span className="font-mono text-sm font-semibold tracking-tight text-foreground">
              EPP
            </span>
            <span className="font-mono text-xs text-muted-foreground">
              · Epistemic Proof Program
            </span>
          </Link>
          <nav className="ml-auto flex items-center gap-4 text-sm">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                isActive
                  ? 'text-foreground'
                  : 'text-muted-foreground transition-colors hover:text-foreground'
              }
            >
              Runs
            </NavLink>
            <NavLink
              to="/onchain"
              className={({ isActive }) =>
                `inline-flex items-center gap-1 ${
                  isActive
                    ? 'text-cyan'
                    : 'text-muted-foreground transition-colors hover:text-foreground'
                }`
              }
            >
              <span aria-hidden="true">⛓</span>
              On-chain
            </NavLink>
            <a
              href="https://epp-verdict-docs.vercel.app"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-muted-foreground transition-colors hover:text-foreground"
            >
              Docs
              <span aria-hidden="true" className="text-[10px]">↗</span>
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/claims" element={<ClaimViewerPage />} />
          <Route path="/flywheel" element={<FlywheelPage />} />
          <Route path="/onchain" element={<OnChainPage />} />
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
