﻿import { render } from '@testing-library/react'
import Home from './Home'

describe('Home Page', () => {
  it('should render without errors', () => {
    const { container } = render(<Home />)
    expect(container.firstChild).toBeInTheDocument()
  })
})
