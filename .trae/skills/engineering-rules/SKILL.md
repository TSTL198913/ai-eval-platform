---
name: "engineering-rules"
description: "Enforces strict engineering principles during development. Invoke before any coding task to ensure compliance with hard constraints, conventions, and testing philosophies."
---

# Engineering Rules Enforcer

This skill enforces strict engineering principles during all development activities. **MUST be invoked at the start of every coding task.**

## Hard Constraints

1. **Evaluator Implementation**: All evaluators must implement `_do_evaluate()` instead of overriding `evaluate()` to ensure circuit breaker and fallback mechanisms work
2. **Validation Tool Reliability**: Validation tools (mutation testing, quality gates) must not be simplified; they must be more reliable than the code they validate
3. **No Hardcoded Values**: Critical logic must use real computed results, not hardcoded values (e.g., A/B testing scores)
4. **Full Implementation**: Functionality must be fully implemented; 'framework-only' implementations are unacceptable

## Engineering Conventions

1. **LLM-as-a-Judge**: Use LLM-as-a-Judge for semantic-level evaluation instead of simple string matching
2. **Multi-dimensional Scores**: Evaluators should return multi-dimensional scores with explainability rather than single scores
3. **Asynchronous Support**: Implement async support natively for I/O-bound evaluators (e.g., those using LLM clients)

## Testing Philosophy

1. **Testing Goals**: Verify business logic correctness, discover production issues; never pursue code coverage for its own sake
2. **Scenario Coverage**: Must cover positive, negative, boundary, exception, and dependency scenarios
3. **Strong Assertions**: Assertions must validate specific business logic; weak assertions (e.g., only checking status) are prohibited
4. **Business Rule Driven**: Without requirements docs, first analyze code to extract business rules and risk points, then design tests around them
5. **Test Code Boundary**: Test code only allowed in tests/ directory; never modify src/ or other business code

## Response Principles

1. **Avoid Overconfidence**: Never make unfounded assumptions; explicitly ask when uncertain
2. **Humility**: Maintain humble response style; acknowledge limitations
3. **Critical Analysis**: Provide thorough analysis of implementation flaws during code review

## Execution Checklist

Before starting any task:
- [ ] Review relevant code context thoroughly
- [ ] Identify potential risks and edge cases
- [ ] Confirm all requirements are understood; ask for clarification if ambiguous
- [ ] Plan implementation with clear milestones
- [ ] Verify after implementation with appropriate tests

Before submitting code:
- [ ] Check compliance with all hard constraints
- [ ] Validate implementation is complete (not framework-only)
- [ ] Ensure critical logic uses real computed results
- [ ] Run tests and verify all scenarios are covered
- [ ] Confirm no business code was modified in tests/ directory
