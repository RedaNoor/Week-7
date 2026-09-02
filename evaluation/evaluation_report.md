# Evaluation Report

## Goal

This report looks at whether the knowledge system retrieves the right source material and avoids making unsupported claims about properties.

## Test set

The evaluation uses a set of questions in test_questions.json covering:

- exact prices
- availability
- bedrooms
- size
- developers
- payment plans
- amenities
- schools
- hospitals
- family suitability
- investment questions
- cases where there is no evidence

## Metrics

### Retrieval accuracy

How often the system pulls the relevant source result.

### Grounding rate

How often the final answer is backed by actual evidence.

### Hallucination rate

How often the answer makes a claim without support.

## Target thresholds

| Metric | Target |
|---|---:|
| Retrieval accuracy | >= 90% |
| Grounding rate | >= 95% |
| Hallucination rate | <= 5% |

## Grounding policy

If the system cannot find verified data, it should not guess. The safer fallback is to say that the information is not available and offer a follow-up with a human rep if needed.

## Final result

These values should be filled in only after running the actual evaluation:

- Retrieval accuracy: TBD
- Grounding rate: TBD
- Hallucination rate: TBD
- Best chunk configuration: TBD
