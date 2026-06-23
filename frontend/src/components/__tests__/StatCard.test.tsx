import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { StatCard } from '@/components/StatCard'
import { Activity, Users, DollarSign, TrendingUp } from 'lucide-react'

describe('StatCard', () => {
  it('should render title and value correctly', () => {
    render(
      <StatCard
        title="测试指标"
        value="测试值"
        icon={<Activity />}
        color="#3b82f6"
      />
    )

    expect(screen.getByText('测试指标')).toBeInTheDocument()
    expect(screen.getByText('测试值')).toBeInTheDocument()
  })

  it('should animate number value from 0 to target', async () => {
    const { container } = render(
      <StatCard
        title="用户数"
        value={1000}
        icon={<Users />}
        color="#10b981"
      />
    )

    expect(screen.getByText('用户数')).toBeInTheDocument()

    await waitFor(
      () => {
        const valueElement = container.querySelector('.text-2xl')
        expect(valueElement).toHaveTextContent('1,000')
      },
      { timeout: 2000 }
    )
  })

  it('should display suffix correctly', () => {
    render(
      <StatCard
        title="准确率"
        value="98.5"
        icon={<TrendingUp />}
        color="#10b981"
        suffix="%"
      />
    )

    expect(screen.getByText('98.5')).toBeInTheDocument()
    expect(screen.getByText('%')).toBeInTheDocument()
  })

  it('should display upward trend correctly', () => {
    render(
      <StatCard
        title="增长率"
        value={15.5}
        icon={<TrendingUp />}
        color="#f59e0b"
        trend={{ value: 5.2, isUp: true }}
      />
    )

    expect(screen.getByText('↑')).toBeInTheDocument()
    expect(screen.getByText('5.2%')).toBeInTheDocument()
    expect(screen.getByText('较上期')).toBeInTheDocument()
  })

  it('should display downward trend correctly', () => {
    render(
      <StatCard
        title="错误率"
        value={2.3}
        icon={<Activity />}
        color="#ef4444"
        trend={{ value: 1.5, isUp: false }}
      />
    )

    expect(screen.getByText('↓')).toBeInTheDocument()
    expect(screen.getByText('1.5%')).toBeInTheDocument()
  })

  it('should apply correct color to icon background', () => {
    const { container } = render(
      <StatCard
        title="成本"
        value={1000}
        icon={<DollarSign />}
        color="#8b5cf6"
      />
    )

    const iconContainer = container.querySelector('.rounded-lg')
    expect(iconContainer).toHaveStyle({ backgroundColor: '#8b5cf615' })
  })

  it('should handle string value without animation', () => {
    render(
      <StatCard
        title="状态"
        value="正常"
        icon={<Activity />}
        color="#10b981"
      />
    )

    expect(screen.getByText('正常')).toBeInTheDocument()
  })
})
