import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { EmptyState, ErrorState } from '@/components/feedback/states';
import { MetricCard } from '@/components/dashboard/metric-card';
import { PaginationBar } from '@/components/common/pagination-bar';
import { SearchToolbar } from '@/components/common/search-toolbar';
import { Calendar } from 'lucide-react';

describe('feedback states', () => {
  it('EmptyState shows title + description + action', () => {
    render(<EmptyState icon={Calendar} title="Nothing here" description="Add one" action={<button>Add</button>} />);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
  });

  it('ErrorState retry button fires onRetry', async () => {
    const onRetry = vi.fn();
    render(<ErrorState description="Boom" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('ErrorState hides retry when no handler', () => {
    render(<ErrorState description="Boom" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});

describe('MetricCard', () => {
  it('renders label, value and hint', () => {
    render(<MetricCard label="Events" value={42} icon={Calendar} hint="total" />);
    expect(screen.getByText('Events')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('total')).toBeInTheDocument();
  });
});

describe('PaginationBar', () => {
  it('hides itself with a single page', () => {
    const { container } = render(<PaginationBar page={1} pageCount={1} onPage={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('disables prev on first page and pages forward', async () => {
    const onPage = vi.fn();
    render(<PaginationBar page={1} pageCount={3} total={25} onPage={onPage} />);
    expect(screen.getByText(/page 1 of 3/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: /next/i }));
    expect(onPage).toHaveBeenCalledWith(2);
  });
});

describe('SearchToolbar', () => {
  it('emits typed value', async () => {
    const onChange = vi.fn();
    render(<SearchToolbar value="" onChange={onChange} placeholder="Search events…" />);
    await userEvent.type(screen.getByLabelText('Search'), 'a');
    expect(onChange).toHaveBeenCalledWith('a');
  });
});
