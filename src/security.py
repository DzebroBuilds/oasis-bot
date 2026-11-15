"""Fail-closed controls for untrusted model output and trading configuration."""
import math


def paper_mode(value):
    # Live trading stays disabled until a durable, account-wide budget exists.
    if str(value).strip().lower() == "false":
        raise ValueError("Live trading is disabled pending durable daily spending controls.")
    return True


def validated_pick(result, market):
    if not isinstance(result, dict) or result.get("skip") is not False:
        return {"skip": True}
    side = result.get("side")
    confidence = result.get("confidence")
    price = market.get("yes_ask" if side == "YES" else "no_ask")
    if side not in ("YES", "NO"):
        return {"skip": True}
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 100:
        return {"skip": True}
    if type(price) is not int or not 1 <= price <= 99:
        return {"skip": True}
    return {"skip": False, "side": side, "confidence": confidence,
            "market_price": price, "ticker": market["ticker"],
            "reasoning": str(result.get("reasoning", ""))[:1000]}
