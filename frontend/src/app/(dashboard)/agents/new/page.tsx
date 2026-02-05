'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';

const strategies = [
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

const personas = [
  { id: 'analytical', name: 'Analytical', description: 'Data-focused, cites specific numbers' },
  { id: 'aggressive', name: 'Aggressive', description: 'Confident, bold statements' },
  { id: 'conservative', name: 'Conservative', description: 'Cautious, emphasizes risk' },
  { id: 'teacher', name: 'Teacher', description: 'Educational, explains reasoning' },
  { id: 'concise', name: 'Concise', description: 'Brief bullet points, just facts' },
];

export default function NewAgentPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    name: '',
    strategy_type: '',
    persona: 'analytical',
    allocated_capital: 10000,
    time_horizon_days: 180,
  });

  const handleCreate = async () => {
    // TODO: Replace with actual API call
    console.log('Creating agent:', formData);
    router.push('/agents');
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
      <div className="flex justify-between mb-8">
        {['Strategy', 'Capital', 'Persona', 'Review'].map((label, i) => (
          <div
            key={label}
            className={`flex items-center gap-2 ${
              i + 1 <= step ? 'text-accent' : 'text-zinc-500'
            }`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center border-2 text-sm font-medium ${
                i + 1 <= step
                  ? 'border-accent bg-accent/10'
                  : 'border-zinc-600'
              }`}
            >
              {i + 1}
            </div>
            <span className="text-sm hidden sm:inline">{label}</span>
          </div>
        ))}
      </div>

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
                onClick={() =>
                  setFormData({ ...formData, strategy_type: strategy.id })
                }
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
                  setFormData({
                    ...formData,
                    allocated_capital: Number(e.target.value),
                  })
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
                  setFormData({
                    ...formData,
                    time_horizon_days: Number(e.target.value),
                  })
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
            <button onClick={() => setStep(3)} className="btn btn-primary">
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Persona */}
      {step === 3 && (
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
                onClick={() => setFormData({ ...formData, persona: persona.id })}
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
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="input"
              placeholder="e.g., Alpha Momentum"
            />
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(2)} className="btn btn-secondary">
              Back
            </button>
            <button
              onClick={() => setStep(4)}
              disabled={!formData.name}
              className="btn btn-primary"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Review */}
      {step === 4 && (
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-semibold mb-2">Review & Create</h2>
            <p className="text-zinc-400">
              Review your agent configuration before creating.
            </p>
          </div>

          <div className="card space-y-3">
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-zinc-400">Name</span>
              <span className="font-medium">{formData.name}</span>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-zinc-400">Strategy</span>
              <span className="font-medium capitalize">
                {formData.strategy_type.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-zinc-400">Capital</span>
              <span className="font-medium">
                ${formData.allocated_capital.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between py-2 border-b border-border">
              <span className="text-zinc-400">Time Horizon</span>
              <span className="font-medium">
                {formData.time_horizon_days} days
              </span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-zinc-400">Persona</span>
              <span className="font-medium capitalize">{formData.persona}</span>
            </div>
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(3)} className="btn btn-secondary">
              Back
            </button>
            <button onClick={handleCreate} className="btn btn-primary">
              Create Agent
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
