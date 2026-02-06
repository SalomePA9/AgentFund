import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-border">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-zinc-50">
            AgentFund
          </Link>
          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm text-zinc-400 hover:text-zinc-50 transition-colors"
            >
              Login
            </Link>
            <Link href="/register" className="btn btn-primary">
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          {/* Glow effect */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-[600px] h-[600px] bg-accent/10 rounded-full blur-3xl" />
          </div>

          <h1 className="relative text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
            Your AI Trading
            <span className="text-gradient"> Team</span>
          </h1>

          <p className="relative text-lg md:text-xl text-zinc-400 mb-10 max-w-2xl mx-auto">
            Deploy autonomous trading agents that execute institutional-grade
            strategies and explain their reasoning in plain language.
          </p>

          <div className="relative flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register" className="btn btn-primary px-8 py-3 text-base">
              Create Your First Agent
            </Link>
            <Link
              href="#how-it-works"
              className="btn btn-secondary px-8 py-3 text-base"
            >
              How It Works
            </Link>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-6 border-t border-border">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">
            Why AgentFund?
          </h2>

          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="card">
              <div className="w-12 h-12 rounded-lg bg-accent-subtle flex items-center justify-center mb-4">
                <svg
                  className="w-6 h-6 text-accent"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Autonomous Execution</h3>
              <p className="text-zinc-400 text-sm">
                Agents monitor markets 24/7, execute trades, and manage risk
                automatically. No manual intervention required.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="card">
              <div className="w-12 h-12 rounded-lg bg-success-subtle flex items-center justify-center mb-4">
                <svg
                  className="w-6 h-6 text-success"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Proven Strategies</h3>
              <p className="text-zinc-400 text-sm">
                Choose from momentum, value, quality, or dividend strategies
                backed by decades of quantitative research.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="card">
              <div className="w-12 h-12 rounded-lg bg-warning-subtle flex items-center justify-center mb-4">
                <svg
                  className="w-6 h-6 text-warning"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-semibold mb-2">Daily Reports</h3>
              <p className="text-zinc-400 text-sm">
                Each agent reports daily in their unique voice, explaining
                trades and market insights in plain language.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-20 px-6 bg-background-secondary">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>

          <div className="space-y-8">
            {/* Step 1 */}
            <div className="flex gap-6 items-start">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-accent flex items-center justify-center text-white font-bold">
                1
              </div>
              <div>
                <h3 className="text-lg font-semibold mb-1">
                  Connect Your Broker
                </h3>
                <p className="text-zinc-400">
                  Link your Alpaca account. Start with paper trading to test
                  strategies risk-free.
                </p>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex gap-6 items-start">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-accent flex items-center justify-center text-white font-bold">
                2
              </div>
              <div>
                <h3 className="text-lg font-semibold mb-1">Create Your Agent</h3>
                <p className="text-zinc-400">
                  Choose a strategy, set your risk parameters, and give your
                  agent a personality.
                </p>
              </div>
            </div>

            {/* Step 3 */}
            <div className="flex gap-6 items-start">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-accent flex items-center justify-center text-white font-bold">
                3
              </div>
              <div>
                <h3 className="text-lg font-semibold mb-1">
                  Watch Them Trade
                </h3>
                <p className="text-zinc-400">
                  Your agents analyze markets, execute trades, and report back
                  with detailed explanations.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Start?</h2>
          <p className="text-zinc-400 mb-8">
            Create your first AI trading agent in under 5 minutes.
          </p>
          <Link href="/register" className="btn btn-primary px-8 py-3 text-base">
            Get Started Free
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-border">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="text-sm text-zinc-500">
            &copy; {new Date().getFullYear()} AgentFund. All rights reserved.
          </div>
          <div className="flex items-center gap-6 text-sm text-zinc-500">
            <Link href="/terms" className="hover:text-zinc-300 transition-colors">
              Terms
            </Link>
            <Link href="/privacy" className="hover:text-zinc-300 transition-colors">
              Privacy
            </Link>
            <Link href="/disclaimer" className="hover:text-zinc-300 transition-colors">
              Risk Disclaimer
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
