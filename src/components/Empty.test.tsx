﻿import { render, screen } from '@testing-library/react'
import Empty from './Empty'

describe('Empty Component', () => {
  it('should render Empty text', () => {
    render(<Empty />)
    expect(screen.getByText('Empty')).toBeInTheDocument()
  })

  it('should have correct className', () => {
    const { container } = render(<Empty />)
    const div = container.querySelector('div')
    expect(div).toHaveClass('flex', 'h-full', 'items-center', 'justify-center')
  })
})
