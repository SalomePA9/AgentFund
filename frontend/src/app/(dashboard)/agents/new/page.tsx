'use client';

import { useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { InlineLoading, ErrorMessage } from '@/components/ui';
import { formatCurrency, formatStrategyType } from '@/lib/utils';
import type { AgentCreate, StrategyType, Persona } from '@/types';

const strategies: { id: StrategyType; name: string; description: string }[] = [
  {
    id: 'momentum',
    name: 'Momentum',
    description:
      'Ride winners, cut losers. Buy stocks with strong recent performance and positive trends.',
  },
  {
    id: 'quality_value',
    name: 'Quality Value',
    description:
      'Find underpriced quality companies. Low valuations with strong fundamentals.',
  },
  {
    id: 'quality_momentum',
    name: 'Quality Momentum',
    description:
      'Best of both worlds. Strong momentum filtered by quality metrics.',
  },
  {
    id: 'dividend_growth',
    name: 'Dividend Growth',
    description:
      'Steady compounders. Companies with long dividend growth track records.',
  },
];

const personas: { id: Persona; name: string; description: string }[] = [
  { id: 'analytical', name: 'Analytical', description: 'Data-focused, cites specific numbers and statistical evidence' },
  { id: 'aggressive', name: 'Aggressive', description: 'Confident, bold statements, conviction-driven' },
  { id: 'conservative', name: 'Conservative', description: 'Cautious, emphasizes risk management and downside protection' },
  { id: 'teacher', name: 'Teacher', description: 'Educational, explains reasoning and market concepts' },
  { id: 'concise', name: 'Concise', description: 'Brief bullet points, just the facts and key takeaways' },
];

const steps = ['Strategy', 'Capital', 'Risk', 'Persona', 'Review'];

interface FormData {
  name: string;
  strategy_type: StrategyType | '';
  persona: Persona;
  allocated_capital: number;
  time_horizon_days: number;
  risk_params: {
    stop_loss_type: string;
    stop_loss_percentage: number;
    max_position_size_pct: number;
    min_risk_reward_ratio: number;
    max_sector_concentration: number;
  };
}

export default function NewAgentPage() {
  const [step, setStep] = useState(1);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdAgentId, setCreatedAgentId] = useState<string | null>(null);
  const [introduction, setIntroduction] = useState<string | null>(null);

  const [formData, setFormData] = useState<FormData>({
    name: '',
    strategy_type: '',
    persona: 'analytical',
    allocated_capital: 10000,
    time_horizon_days: 180,
    risk_params: {
      stop_loss_type: 'percentage',
      stop_loss_percentage: 8,
      max_position_size_pct: 15,
      min_risk_reward_ratio: 2,
      max_sector_concentration: 30,
    },
  });

  const updateForm = (updates: Partial<FormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }));
  };

  const updateRisk = (updates: Partial<FormData['risk_params']>) => {
    setFormData((prev) => ({
      ...prev,
      risk_params: { ...prev.risk_params, ...updates },
    }));
  };

  const handleCreate = async () => {
    if (!formData.strategy_type) return;

    setIsCreating(true);
    setError(null);
    try {
      const payload: AgentCreate = {
        name: formData.name,
        strategy_type: formData.strategy_type,
        persona: formData.persona,
        allocated_capital: formData.allocated_capital,
        time_horizon_days: formData.time_horizon_days,
        risk_params: formData.risk_params,
      };

      const agent = await api.agents.create(payload);
      setCreatedAgentId(agent.id);

      // Try to get LLM introduction
      try {
        const chatResponse = await api.chat.sendMessage(
          agent.id,
          'Introduce yourself. What is your name, trading strategy, and how will you approach the market?'
        );
        setIntroduction(chatResponse.agent_response.message);
      } catch {
        // LLM intro is optional
        setIntroduction(null);
      }

      setStep(6); // Show introduction/success screen
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create agent');
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Link href="/agents" className="text-zinc-400 hover:text-zinc-50 text-sm">
          &larr; Back to Agents
        </Link>
        <h1 className="text-2xl font-bold mt-4">Create New Agent</h1>
      </div>

      {/* Progress */}
      {step <= 5 && (
        <div className="flex justify-between mb-8">
          {steps.map((label, i) => (
            <div
              key={label}
              className={`flex items-center gap-2 ${
                i + 1 <= step ? 'text-accent' : 'text-zinc-500'
              }`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center border-2 text-sm font-medium ${
                  i + 1 < step
                    ? 'border-accent bg-accent text-white'
                    : i + 1 === step
                    ? 'border-accent bg-accent/10'
                    : 'border-zinc-600'
                }`}
              >
                {i + 1 < step ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span className="text-sm hidden sm:inline">{label}</span>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-6">
          <ErrorMessage message={error} />
        </div>
      )}

      {/* Step 1: Strategy */}
      {step === 1 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold mb-2">Choose a Strategy</h2>
            <p className="text-zinc-400">
              Select the trading approach your agent will use.
            </p>
          </div>

          <div className="space-y-3">
            {strategies.map((strategy) => (
              <button
                key={strategy.id}
                onClick={() => updateForm({ strategy_type: strategy.id })}
                className={`w-full p-4 text-left rounded-lg border transition-all ${
                  formData.strategy_type === strategy.id
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-zinc-500'
                }`}
              >
                <div className="font-medium">{strategy.name}</div>
                <div className="text-sm text-zinc-400 mt-1">
                  {strategy.description}
                </div>
              </button>
            ))}
          </div>

          <div className="flex justify-end">
            <button
              onClick={() => setStep(2)}
              disabled={!formData.strategy_type}
              className="btn btn-primary"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Capital */}
      {step === 2 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold mb-2">Allocate Capital</h2>
            <p className="text-zinc-400">
              Set the amount and time horizon for this agent.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Amount to Allocate
              </label>
              <input
                type="number"
                value={formData.allocated_capital}
                onChange={(e) =>
                  updateForm({ allocated_capital: Number(e.target.value) })
                }
                className="input"
                min={1000}
              />
              <p className="text-xs text-zinc-500 mt-1">Minimum: $1,000</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Time Horizon
              </label>
              <select
                value={formData.time_horizon_days}
                onChange={(e) =>
                  updateForm({ time_horizon_days: Number(e.target.value) })
                }
                className="input"
              >
                <option value={90}>3 months</option>
                <option value={180}>6 months</option>
                <option value={365}>1 year</option>
                <option value={730}>2 years</option>
              </select>
            </div>
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(1)} className="btn btn-secondary">
              Back
            </button>
            <button
              onClick={() => setStep(3)}
              className="btn btn-primary"
              disabled={formData.allocated_capital < 1000}
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Risk Parameters */}
      {step === 3 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold mb-2">Risk Management</h2>
            <p className="text-zinc-400">
              Configure how aggressively your agent manages risk.
            </p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Stop Loss Type
              </label>
              <select
                value={formData.risk_params.stop_loss_type}
                onChange={(e) => updateRisk({ stop_loss_type: e.target.value })}
                className="input"
              >
                <option value="percentage">Percentage</option>
                <option value="ma_200">200-Day Moving Average</option>
                <option value="atr">ATR-Based</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Stop Loss Percentage
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={2}
                  max={20}
                  step={1}
                  value={formData.risk_params.stop_loss_percentage}
                  onChange={(e) =>
                    updateRisk({ stop_loss_percentage: Number(e.target.value) })
                  }
                  className="flex-1"
                />
                <span className="text-sm text-number w-12 text-right">
                  {formData.risk_params.stop_loss_percentage}%
                </span>
              </div>
              <p className="text-xs text-zinc-500 mt-1">
                Exit position if it drops by this percentage
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Max Position Size
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={5}
                  max={40}
                  step={5}
                  value={formData.risk_params.max_position_size_pct}
                  onChange={(e) =>
                    updateRisk({ max_position_size_pct: Number(e.target.value) })
                  }
                  className="flex-1"
                />
                <span className="text-sm text-number w-12 text-right">
                  {formData.risk_params.max_position_size_pct}%
                </span>
              </div>
              <p className="text-xs text-zinc-500 mt-1">
                Maximum % of capital in a single position
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Minimum Risk/Reward Ratio
              </label>
              <select
                value={formData.risk_params.min_risk_reward_ratio}
                onChange={(e) =>
                  updateRisk({ min_risk_reward_ratio: Number(e.target.value) })
                }
                className="input"
              >
                <option value={1.5}>1.5:1</option>
                <option value={2}>2:1</option>
                <option value={2.5}>2.5:1</option>
                <option value={3}>3:1</option>
              </select>
              <p className="text-xs text-zinc-500 mt-1">
                Only enter trades with this potential upside vs downside
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-2">
                Max Sector Concentration
              </label>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={20}
                  max={60}
                  step={5}
                  value={formData.risk_params.max_sector_concentration}
                  onChange={(e) =>
                    updateRisk({ max_sector_concentration: Number(e.target.value) })
                  }
                  className="flex-1"
                />
                <span className="text-sm text-number w-12 text-right">
                  {formData.risk_params.max_sector_concentration}%
                </span>
              </div>
              <p className="text-xs text-zinc-500 mt-1">
                Maximum % of portfolio in any single sector
              </p>
            </div>
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(2)} className="btn btn-secondary">
              Back
            </button>
            <button onClick={() => setStep(4)} className="btn btn-primary">
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Persona */}
      {step === 4 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold mb-2">Choose a Persona</h2>
            <p className="text-zinc-400">
              Select how your agent communicates with you.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {personas.map((persona) => (
              <button
                key={persona.id}
                onClick={() => updateForm({ persona: persona.id })}
                className={`p-4 text-left rounded-lg border transition-all ${
                  formData.persona === persona.id
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-zinc-500'
                }`}
              >
                <div className="font-medium">{persona.name}</div>
                <div className="text-xs text-zinc-400 mt-1">
                  {persona.description}
                </div>
              </button>
            ))}
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">
              Agent Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => updateForm({ name: e.target.value })}
              className="input"
              placeholder="e.g., Alpha Momentum"
            />
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(3)} className="btn btn-secondary">
              Back
            </button>
            <button
              onClick={() => setStep(5)}
              disabled={!formData.name}
              className="btn btn-primary"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 5: Review */}
      {step === 5 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold mb-2">Review & Create</h2>
            <p className="text-zinc-400">
              Review your agent configuration before creating.
            </p>
          </div>

          <div className="card space-y-3">
            <ReviewRow label="Name" value={formData.name} />
            <ReviewRow
              label="Strategy"
              value={formData.strategy_type ? formatStrategyType(formData.strategy_type) : '-'}
            />
            <ReviewRow
              label="Capital"
              value={formatCurrency(formData.allocated_capital)}
            />
            <ReviewRow
              label="Time Horizon"
              value={`${formData.time_horizon_days} days`}
            />
            <ReviewRow
              label="Persona"
              value={formData.persona.charAt(0).toUpperCase() + formData.persona.slice(1)}
            />
          </div>

          <div className="card space-y-3">
            <h3 className="text-sm font-medium text-zinc-300 mb-2">Risk Parameters</h3>
            <ReviewRow
              label="Stop Loss"
              value={`${formData.risk_params.stop_loss_percentage}% (${formData.risk_params.stop_loss_type})`}
            />
            <ReviewRow
              label="Max Position Size"
              value={`${formData.risk_params.max_position_size_pct}%`}
            />
            <ReviewRow
              label="Risk/Reward Ratio"
              value={`${formData.risk_params.min_risk_reward_ratio}:1`}
            />
            <ReviewRow
              label="Max Sector Concentration"
              value={`${formData.risk_params.max_sector_concentration}%`}
              noBorder
            />
          </div>

          <div className="flex justify-between">
            <button
              onClick={() => setStep(4)}
              className="btn btn-secondary"
              disabled={isCreating}
            >
              Back
            </button>
            <button
              onClick={handleCreate}
              className="btn btn-primary"
              disabled={isCreating}
            >
              {isCreating ? <InlineLoading text="Creating agent..." /> : 'Create Agent'}
            </button>
          </div>
        </div>
      )}

      {/* Step 6: Success / Introduction */}
      {step === 6 && createdAgentId && (
        <div className="space-y-6">
          <div className="text-center">
            <div className="w-16 h-16 rounded-full bg-success-subtle flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold">
              {formData.name} is ready!
            </h2>
            <p className="text-zinc-400 mt-1">
              Your agent has been created and is ready to start trading.
            </p>
          </div>

          {/* LLM Introduction */}
          {introduction && (
            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-accent/20 flex items-center justify-center text-accent text-sm font-bold">
                  {formData.name.charAt(0)}
                </div>
                <span className="font-medium">{formData.name}</span>
              </div>
              <div className="text-sm text-zinc-300 whitespace-pre-wrap leading-relaxed">
                {introduction}
              </div>
            </div>
          )}

          <div className="flex justify-center gap-3">
            <Link
              href={`/agents/${createdAgentId}`}
              className="btn btn-primary"
            >
              View Agent
            </Link>
            <Link
              href={`/agents/${createdAgentId}/chat`}
              className="btn btn-secondary"
            >
              Start Chatting
            </Link>
            <Link href="/agents" className="btn btn-ghost">
              Back to Agents
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewRow({
  label,
  value,
  noBorder,
}: {
  label: string;
  value: string;
  noBorder?: boolean;
}) {
  return (
    <div
      className={`flex justify-between py-2 ${
        noBorder ? '' : 'border-b border-border'
      }`}
    >
      <span className="text-zinc-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
