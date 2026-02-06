'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { api } from '@/lib/api';
import { PageLoading, ErrorMessage, InlineLoading } from '@/components/ui';
import type { BrokerStatus } from '@/types';

export default function SettingsPage() {
  const { user, loadUser } = useAuthStore();
  const [settings, setSettings] = useState({
    timezone: 'America/New_York',
    report_time: '07:00',
    email_reports: true,
    email_alerts: true,
  });
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);

  const [brokerStatus, setBrokerStatus] = useState<BrokerStatus | null>(null);
  const [brokerLoading, setBrokerLoading] = useState(true);
  const [brokerError, setBrokerError] = useState<string | null>(null);

  const [connectForm, setConnectForm] = useState({
    apiKey: '',
    apiSecret: '',
    paperMode: true,
  });
  const [connecting, setConnecting] = useState(false);

  // Load user settings
  useEffect(() => {
    if (user?.settings) {
      setSettings({
        timezone: user.settings.timezone || 'America/New_York',
        report_time: user.settings.report_time || '07:00',
        email_reports: user.settings.email_reports ?? true,
        email_alerts: user.settings.email_alerts ?? true,
      });
    }
  }, [user]);

  // Load broker status
  useEffect(() => {
    const fetchBrokerStatus = async () => {
      setBrokerLoading(true);
      try {
        const status = await api.broker.getStatus();
        setBrokerStatus(status);
      } catch {
        setBrokerStatus({ connected: false, paper_mode: null, account_id: null, status: null, portfolio_value: null, cash: null, buying_power: null });
      } finally {
        setBrokerLoading(false);
      }
    };
    fetchBrokerStatus();
  }, []);

  const handleSaveSettings = async () => {
    setSettingsSaving(true);
    setSettingsMessage(null);
    try {
      await api.auth.updateSettings(settings);
      await loadUser();
      setSettingsMessage('Settings saved');
      setTimeout(() => setSettingsMessage(null), 3000);
    } catch (err) {
      setSettingsMessage(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSettingsSaving(false);
    }
  };

  const handleConnect = async () => {
    if (!connectForm.apiKey || !connectForm.apiSecret) return;
    setConnecting(true);
    setBrokerError(null);
    try {
      const status = await api.broker.connect(
        connectForm.apiKey,
        connectForm.apiSecret,
        connectForm.paperMode
      );
      setBrokerStatus(status);
      setConnectForm({ apiKey: '', apiSecret: '', paperMode: true });
    } catch (err) {
      setBrokerError(err instanceof Error ? err.message : 'Connection failed');
    } finally {
      setConnecting(false);
    }
  };

  const handleSwitchMode = async () => {
    try {
      const status = await api.broker.switchMode();
      setBrokerStatus(status);
    } catch (err) {
      setBrokerError(err instanceof Error ? err.message : 'Failed to switch mode');
    }
  };

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

        {brokerLoading ? (
          <InlineLoading text="Checking broker status..." />
        ) : brokerStatus?.connected ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-success/10 rounded-lg border border-success/30">
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-success" />
                <span className="font-medium">Alpaca Connected</span>
              </div>
              <span className="badge badge-success">
                {brokerStatus.paper_mode ? 'Paper' : 'Live'}
              </span>
            </div>

            {brokerStatus.portfolio_value !== null && (
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-zinc-500">Portfolio Value</div>
                  <div className="font-medium text-number">
                    ${brokerStatus.portfolio_value?.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-zinc-500">Cash</div>
                  <div className="font-medium text-number">
                    ${brokerStatus.cash?.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-zinc-500">Buying Power</div>
                  <div className="font-medium text-number">
                    ${brokerStatus.buying_power?.toLocaleString()}
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleSwitchMode}
                className="btn btn-secondary text-sm"
              >
                Switch to {brokerStatus.paper_mode ? 'Live' : 'Paper'}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-zinc-400 text-sm">
              Connect your Alpaca account to enable trading.
            </p>

            {brokerError && <ErrorMessage message={brokerError} />}

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  API Key
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="PK..."
                  value={connectForm.apiKey}
                  onChange={(e) =>
                    setConnectForm({ ...connectForm, apiKey: e.target.value })
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">
                  API Secret
                </label>
                <input
                  type="password"
                  className="input"
                  placeholder="Enter your API secret"
                  value={connectForm.apiSecret}
                  onChange={(e) =>
                    setConnectForm({ ...connectForm, apiSecret: e.target.value })
                  }
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="paper-mode"
                  checked={connectForm.paperMode}
                  onChange={(e) =>
                    setConnectForm({ ...connectForm, paperMode: e.target.checked })
                  }
                  className="w-4 h-4 rounded border-border bg-background"
                />
                <label htmlFor="paper-mode" className="text-sm text-zinc-300">
                  Use paper trading (recommended for testing)
                </label>
              </div>
            </div>

            <button
              onClick={handleConnect}
              className="btn btn-primary"
              disabled={connecting || !connectForm.apiKey || !connectForm.apiSecret}
            >
              {connecting ? <InlineLoading text="Connecting..." /> : 'Connect Alpaca'}
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
              <option value="UTC">UTC</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleSaveSettings}
              className="btn btn-primary text-sm"
              disabled={settingsSaving}
            >
              {settingsSaving ? <InlineLoading text="Saving..." /> : 'Save Preferences'}
            </button>
            {settingsMessage && (
              <span className="text-sm text-success">{settingsMessage}</span>
            )}
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
              value={user?.email ?? ''}
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
