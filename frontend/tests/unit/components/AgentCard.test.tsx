import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// =============================================================================
// AgentCard Component Tests
// Tests for the trading agent display card component
// =============================================================================

interface Agent {
  id: string;
  name: string;
  strategy: 'growth' | 'value' | 'momentum' | 'dividend' | 'custom';
  status: 'active' | 'paused' | 'stopped';
  allocated_capital: number;
  current_value: number;
  total_return: number;
  win_rate: number;
  risk_tolerance: 'low' | 'medium' | 'high';
}

interface AgentCardProps {
  agent: Agent;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onDelete?: (id: string) => void;
  onClick?: (id: string) => void;
}

// Mock AgentCard component
function AgentCard({ agent, onPause, onResume, onDelete, onClick }: AgentCardProps) {
  const statusColors = {
    active: 'bg-green-500',
    paused: 'bg-yellow-500',
    stopped: 'bg-red-500',
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

  const formatPercent = (val: number) =>
    `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;

  return (
    <div
      className="agent-card bg-gray-900 rounded-xl p-6 cursor-pointer hover:bg-gray-800"
      onClick={() => onClick?.(agent.id)}
      role="article"
      aria-label={`Agent: ${agent.name}`}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{agent.name}</h3>
          <span className="text-sm text-gray-400 capitalize">{agent.strategy}</span>
        </div>
        <span
          className={`status-badge px-2 py-1 rounded-full text-xs ${statusColors[agent.status]}`}
          data-testid="status-badge"
        >
          {agent.status}
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between">
          <span className="text-gray-400">Capital</span>
          <span className="text-white">{formatCurrency(agent.allocated_capital)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Current Value</span>
          <span className="text-white">{formatCurrency(agent.current_value)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Total Return</span>
          <span className={agent.total_return >= 0 ? 'text-green-400' : 'text-red-400'}>
            {formatPercent(agent.total_return)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Win Rate</span>
          <span className="text-white">{agent.win_rate.toFixed(1)}%</span>
        </div>
      </div>

      <div className="flex gap-2 mt-4" onClick={(e) => e.stopPropagation()}>
        {agent.status === 'active' ? (
          <button
            className="pause-btn flex-1 bg-yellow-600 text-white py-2 rounded-lg"
            onClick={() => onPause?.(agent.id)}
          >
            Pause
          </button>
        ) : (
          <button
            className="resume-btn flex-1 bg-green-600 text-white py-2 rounded-lg"
            onClick={() => onResume?.(agent.id)}
          >
            Resume
          </button>
        )}
        <button
          className="delete-btn flex-1 bg-red-600 text-white py-2 rounded-lg"
          onClick={() => onDelete?.(agent.id)}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

// =============================================================================
// Test Data
// =============================================================================
const mockActiveAgent: Agent = {
  id: 'agent-1',
  name: 'Growth AI',
  strategy: 'growth',
  status: 'active',
  allocated_capital: 25000,
  current_value: 26500,
  total_return: 6.0,
  win_rate: 72.5,
  risk_tolerance: 'medium',
};

const mockPausedAgent: Agent = {
  ...mockActiveAgent,
  id: 'agent-2',
  name: 'Value Hunter',
  strategy: 'value',
  status: 'paused',
  total_return: -2.5,
};

// =============================================================================
// Tests
// =============================================================================
describe('AgentCard Component', () => {
  describe('Rendering', () => {
    it('renders agent name and strategy', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      expect(screen.getByText('Growth AI')).toBeInTheDocument();
      expect(screen.getByText('growth')).toBeInTheDocument();
    });

    it('renders status badge with correct color', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent('active');
      expect(badge).toHaveClass('bg-green-500');
    });

    it('renders paused status with yellow color', () => {
      render(<AgentCard agent={mockPausedAgent} />);

      const badge = screen.getByTestId('status-badge');
      expect(badge).toHaveTextContent('paused');
      expect(badge).toHaveClass('bg-yellow-500');
    });

    it('renders financial metrics correctly', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      expect(screen.getByText('$25,000.00')).toBeInTheDocument();
      expect(screen.getByText('$26,500.00')).toBeInTheDocument();
      expect(screen.getByText('+6.00%')).toBeInTheDocument();
      expect(screen.getByText('72.5%')).toBeInTheDocument();
    });

    it('shows negative returns with red color', () => {
      render(<AgentCard agent={mockPausedAgent} />);

      const returnElement = screen.getByText('-2.50%');
      expect(returnElement).toHaveClass('text-red-400');
    });

    it('shows positive returns with green color', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      const returnElement = screen.getByText('+6.00%');
      expect(returnElement).toHaveClass('text-green-400');
    });
  });

  describe('Actions', () => {
    it('shows Pause button for active agents', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /resume/i })).not.toBeInTheDocument();
    });

    it('shows Resume button for paused agents', () => {
      render(<AgentCard agent={mockPausedAgent} />);

      expect(screen.getByRole('button', { name: /resume/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /pause/i })).not.toBeInTheDocument();
    });

    it('always shows Delete button', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
    });

    it('calls onPause with agent id when Pause is clicked', async () => {
      const handlePause = vi.fn();
      const user = userEvent.setup();

      render(<AgentCard agent={mockActiveAgent} onPause={handlePause} />);
      await user.click(screen.getByRole('button', { name: /pause/i }));

      expect(handlePause).toHaveBeenCalledWith('agent-1');
    });

    it('calls onResume with agent id when Resume is clicked', async () => {
      const handleResume = vi.fn();
      const user = userEvent.setup();

      render(<AgentCard agent={mockPausedAgent} onResume={handleResume} />);
      await user.click(screen.getByRole('button', { name: /resume/i }));

      expect(handleResume).toHaveBeenCalledWith('agent-2');
    });

    it('calls onDelete with agent id when Delete is clicked', async () => {
      const handleDelete = vi.fn();
      const user = userEvent.setup();

      render(<AgentCard agent={mockActiveAgent} onDelete={handleDelete} />);
      await user.click(screen.getByRole('button', { name: /delete/i }));

      expect(handleDelete).toHaveBeenCalledWith('agent-1');
    });

    it('calls onClick with agent id when card is clicked', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();

      render(<AgentCard agent={mockActiveAgent} onClick={handleClick} />);
      await user.click(screen.getByRole('article'));

      expect(handleClick).toHaveBeenCalledWith('agent-1');
    });

    it('does not trigger card onClick when action buttons are clicked', async () => {
      const handleClick = vi.fn();
      const handlePause = vi.fn();
      const user = userEvent.setup();

      render(
        <AgentCard
          agent={mockActiveAgent}
          onClick={handleClick}
          onPause={handlePause}
        />
      );
      await user.click(screen.getByRole('button', { name: /pause/i }));

      expect(handlePause).toHaveBeenCalled();
      expect(handleClick).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has correct aria-label', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      expect(screen.getByRole('article')).toHaveAttribute(
        'aria-label',
        'Agent: Growth AI'
      );
    });

    it('all buttons are accessible', () => {
      render(<AgentCard agent={mockActiveAgent} />);

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBe(2); // Pause and Delete
    });
  });
});
