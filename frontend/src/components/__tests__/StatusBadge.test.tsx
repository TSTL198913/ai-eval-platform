import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { StatusBadge } from '@/components/StatusBadge'

describe('StatusBadge', () => {
  it('should render healthy status with correct styling', () => {
    render(<StatusBadge status="healthy" />)

    const badge = screen.getByText('健康')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#10b981' })
  })

  it('should render unhealthy status with correct styling', () => {
    render(<StatusBadge status="unhealthy" />)

    const badge = screen.getByText('异常')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#ef4444' })
  })

  it('should render degraded status with correct styling', () => {
    render(<StatusBadge status="degraded" />)

    const badge = screen.getByText('降级')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#f59e0b' })
  })

  it('should render pending status with correct styling', () => {
    render(<StatusBadge status="pending" />)

    const badge = screen.getByText('待处理')
    expect(badge).toBeInTheDocument()
  })

  it('should render running status with correct styling', () => {
    render(<StatusBadge status="running" />)

    const badge = screen.getByText('运行中')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#3b82f6' })
  })

  it('should render completed status with correct styling', () => {
    render(<StatusBadge status="completed" />)

    const badge = screen.getByText('已完成')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#10b981' })
  })

  it('should render failed status with correct styling', () => {
    render(<StatusBadge status="failed" />)

    const badge = screen.getByText('失败')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#ef4444' })
  })

  it('should render active status with correct styling', () => {
    render(<StatusBadge status="active" />)

    const badge = screen.getByText('活跃')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#10b981' })
  })

  it('should render inactive status with correct styling', () => {
    render(<StatusBadge status="inactive" />)

    const badge = screen.getByText('停用')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#9ca3af' })
  })

  it('should render unknown status as-is', () => {
    render(<StatusBadge status="unknown_status" />)

    const badge = screen.getByText('unknown_status')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveStyle({ color: '#6b7280' })
  })

  it('should apply small size without animation', () => {
    const { container } = render(<StatusBadge status="healthy" size="small" />)

    const dot = container.querySelector('.w-1\\.5')
    expect(dot).not.toHaveClass('animate-pulse')
  })

  it('should apply medium size with animation', () => {
    const { container } = render(<StatusBadge status="healthy" size="medium" />)

    const dot = container.querySelector('.w-1\\.5')
    expect(dot).toHaveClass('animate-pulse')
  })
})
