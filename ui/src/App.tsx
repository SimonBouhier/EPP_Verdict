import { Link, NavLink, Route, Routes } from 'react-router-dom';
import ClaimViewerPage from '@/routes/claim-viewer';
import FlywheelPage from '@/routes/flywheel';
import HomePage from '@/routes/home';
import OnChainPage from '@/routes/onchain';
import opalEmblem from '@/assets/opal.svg';

export default function App() {
  return (
    <div className="opal-archive min-h-screen text-foreground antialiased">
      <header className="border-b border-border bg-background/80 backdrop-blur">
        <div className="archive-nav mx-auto flex min-h-16 max-w-6xl flex-wrap items-center gap-y-3 px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <img src={opalEmblem} alt="" width="32" height="32" />
            <span className="text-sm font-medium tracking-[.15em] text-foreground">
              EPP
            </span>
            <span className="archive-wordmark text-xs text-muted-foreground">
              · Historical archive
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
              Past runs
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
              Devnet archive
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

      <main className="mx-auto max-w-6xl px-4 py-8">
        <aside className="archive-context mb-8 border-l-2 border-cyan/40 px-4 py-2 text-xs leading-relaxed" aria-label="Archive status">
          <p className="font-medium text-foreground">Historical demonstration — blockchain publication retired</p>
          <p className="mt-1 text-muted-foreground">
            These saved runs describe earlier experiments. This site executes no models and does not report current performance.
            EPP now serves as a local, personal attestation engine.{' '}
            <a href="https://epp-verdict-docs.vercel.app/current-status/" className="text-cyan underline underline-offset-2">
              Read the current scope and evidence
            </a>.
          </p>
        </aside>
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
        <div className="mx-auto flex min-h-16 max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs text-muted-foreground">
          <span className="font-mono">EPP archive · MIT</span>
          <span className="font-mono">Historical data · read only</span>
        </div>
      </footer>
    </div>
  );
}
