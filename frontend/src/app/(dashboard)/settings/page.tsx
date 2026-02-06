'use client';

import { useState } from 'react';

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    timezone: 'America/New_York',
    report_time: '07:00',
    email_reports: true,
    email_alerts: true,
  });

  const [brokerConnected, setBrokerConnected] = useState(false);
  const [paperMode, setPaperMode] = useState(true);

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-zinc-400 mt-1">
          Manage your account and preferences
        </p>
      </div>

      {/* Broker Connection */}
      <section className="card">
        <h2 className="text-lg font-semibold mb-4">Broker Connection</h2>

        {brokerConnected ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-success/10 rounded-lg border border-success/30">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-success" />
                <span className="font-medium">Alpaca Connected</span>
              </div>
              <span className="badge badge-success">
                {paperMode ? 'Paper' : 'Live'}
              </span>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setPaperMode(!paperMode)}
                className="btn btn-secondary text-sm"
              >
                Switch to {paperMode ? 'Live' : 'Paper'}
              </button>
              <button
                onClick={() => setBrokerConnected(false)}
                className="btn btn-ghost text-sm"
              >
                Disconnect
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-zinc-400 text-sm">
              Connect your Alpaca account to enable trading.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  API Key
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="PK..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  API Secret
                </label>
                <input
                  type="password"
                  className="input"
                  placeholder="••••••••••••"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="paper-mode"
                  checked={paperMode}
                  onChange={(e) => setPaperMode(e.target.checked)}
                  className="w-4 h-4 rounded border-border bg-background"
                />
                <label htmlFor="paper-mode" className="text-sm text-zinc-300">
                  Use paper trading (recommended for testing)
                </label>
              </div>
            </div>

            <button
              onClick={() => setBrokerConnected(true)}
              className="btn btn-primary"
            >
              Connect Alpaca
            </button>
          </div>
        )}
      </section>

      {/* Notifications */}
      <section className="card">
        <h2 className="text-lg font-semibold mb-4">Notifications</h2>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Daily Reports</div>
              <div className="text-sm text-zinc-400">
                Receive daily agent reports via email
              </div>
            </div>
            <Toggle
              checked={settings.email_reports}
              onChange={(checked) =>
                setSettings({ ...settings, email_reports: checked })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium">Trade Alerts</div>
              <div className="text-sm text-zinc-400">
                Get notified when agents execute trades
              </div>
            </div>
            <Toggle
              checked={settings.email_alerts}
              onChange={(checked) =>
                setSettings({ ...settings, email_alerts: checked })
              }
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Report Delivery Time
            </label>
            <select
              value={settings.report_time}
              onChange={(e) =>
                setSettings({ ...settings, report_time: e.target.value })
              }
              className="input w-auto"
            >
              <option value="06:00">6:00 AM</option>
              <option value="07:00">7:00 AM</option>
              <option value="08:00">8:00 AM</option>
              <option value="09:00">9:00 AM</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Timezone
            </label>
            <select
              value={settings.timezone}
              onChange={(e) =>
                setSettings({ ...settings, timezone: e.target.value })
              }
              className="input w-auto"
            >
              <option value="America/New_York">Eastern (ET)</option>
              <option value="America/Chicago">Central (CT)</option>
              <option value="America/Denver">Mountain (MT)</option>
              <option value="America/Los_Angeles">Pacific (PT)</option>
            </select>
          </div>
        </div>
      </section>

      {/* Account */}
      <section className="card">
        <h2 className="text-lg font-semibold mb-4">Account</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Email
            </label>
            <input
              type="email"
              className="input"
              value="user@example.com"
              disabled
            />
          </div>

          <button className="btn btn-secondary text-sm">Change Password</button>
        </div>
      </section>

      {/* Danger Zone */}
      <section className="card border-error/30">
        <h2 className="text-lg font-semibold text-error mb-4">Danger Zone</h2>

        <div className="flex items-center justify-between">
          <div>
            <div className="font-medium">Delete Account</div>
            <div className="text-sm text-zinc-400">
              Permanently delete your account and all data
            </div>
          </div>
          <button className="btn btn-destructive text-sm">Delete Account</button>
        </div>
      </section>
    </div>
  );
}

function Toggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-11 h-6 rounded-full transition-colors ${
        checked ? 'bg-accent' : 'bg-zinc-600'
      }`}
    >
      <span
        className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}
