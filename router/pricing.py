from openai.types.responses import ResponseUsage

from config.settings import PricingSettings


def compute_cost(usage: ResponseUsage, pricing: PricingSettings) -> float:
    """USD cost of one model call, from the token counts the API reports."""
    tier = (
        pricing.long_context
        if usage.input_tokens > pricing.long_context_threshold_tokens
        else pricing.short_context
    )
    # cached and cache-write tokens are both counted inside input_tokens
    cached = usage.input_tokens_details.cached_tokens
    cache_write = usage.input_tokens_details.cache_write_tokens or 0
    uncached = usage.input_tokens - cached - cache_write

    cost = (
        uncached * tier.input
        + cached * tier.cached_input
        + cache_write * tier.cache_write
        + usage.output_tokens * tier.output
    )
    return cost / pricing.tokens_per_price_unit
