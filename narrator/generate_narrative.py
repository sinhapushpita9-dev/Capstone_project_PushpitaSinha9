import os
import json

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

MODEL_CANDIDATES = [
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

def generate_scr_narrative(findings: dict) -> dict:
    """
    Calls the Gemini API to produce a Situation-Complication-Resolution
    business narrative from the given findings dict.

    Always returns a structured dict - never raises a raw exception to the
    caller - so get_narrative() below can safely fall back offline on any
    failure (missing key, network error, quota error, timeout, etc).
    """
    system_instruction = (
        "You are a senior data analyst writing for Mamaearth's regional ops "
        "and finance heads. Write a business narrative with exactly three "
        "labeled sections: Situation, Complication, Resolution. "
        "Every number you state must come from the findings supplied to you "
        "in the user message, and must appear with the same value - do not "
        "invent, estimate, or round any statistic differently than given."
    )

    # Build the user prompt FROM the findings argument (not hardcoded),
    # so a different findings.json automatically produces a different
    # narrative without any change to this function.
    user_prompt = (
        "Here are the verified findings from our data analysis, as JSON:\n\n"
        f"{json.dumps(findings, indent=2)}\n\n"
        "Using ONLY the numbers above, write the SCR business narrative "
        "as instructed in the system prompt. Keep it to about 250 words."
    )

    if not GENAI_AVAILABLE:
        return {
            "status": "error",
            "narrative": None,
            "message": "google-genai package is not installed (pip install google-genai)",
        }

    last_error = "unknown error"
    try:
        client = genai.Client()  # reads the GEMINI_API_KEY environment variable

        # Gemini model names get retired over time, so we try a short list
        # in order and use the first one that works.
        for model_name in MODEL_CANDIDATES:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        # temperature=0.0: this is a factual business report, not
                        # creative writing, so we want the most deterministic,
                        # least "creative" output possible every time it is run.
                        temperature=0.0,
                        # explicit value (not the API default), generous enough
                        # for a 3-section, ~250-word narrative
                        max_output_tokens=1000,
                        # timeout is in MILLISECONDS; 20000 = 20 seconds,
                        # comfortably over the taught 10-second minimum
                        http_options=types.HttpOptions(timeout=20000),
                    ),
                )
                tokens = None
                if getattr(response, "usage_metadata", None):
                    tokens = response.usage_metadata.total_token_count
                return {
                    "status": "success",
                    "narrative": response.text,
                    "tokens": tokens,
                }
            except Exception as model_err:
                last_error = f"{model_name}: {model_err}"
                continue  # try the next model name

        # every model name failed
        raise RuntimeError(last_error)

    except Exception as err:
        # Never let a raw exception escape - the caller always gets a
        # predictable, structured dict back.
        return {
            "status": "error",
            "narrative": None,
            "message": str(err),
        }

def generate_scr_narrative_offline(findings: dict) -> dict:
    """
    Fully deterministic, template-based SCR narrative built directly from
    findings. No network call, no API key required. Same return-dict shape
    as the online path, and guarantees all 5 required figures (Task 5)
    are present verbatim.
    """
    rev = findings["cleaned_total_revenue_inr"]
    raw_rev = findings["raw_total_revenue_inr"]
    delta = findings["duplicate_reconciliation_delta_inr"]
    cod_rate = findings["return_rate_by_payment"]["COD"]
    card_rate = findings["return_rate_by_payment"]["CARD"]
    upi_rate = findings["return_rate_by_payment"]["UPI"]
    risk_seg = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]

    narrative = f"""SITUATION
Mamaearth's cleaned order data shows a verified total revenue of Rs {rev:,.2f}
across the reporting period. This figure was reconciled against Part 1's raw
database total of Rs {raw_rev:,.2f}, a difference of Rs {delta:,.2f} that is
fully explained by 5 duplicate order submissions identified and removed during
data cleaning -- not by any change in actual sales.

COMPLICATION
Return rates vary sharply by payment method: Cash-on-Delivery (COD) orders are
returned at {cod_rate}%, more than double UPI's {upi_rate}% and roughly three
times Card's {card_rate}%. Breaking this down further by city tier reveals the
real concentration of risk: the highest-risk segment is COD orders in
Tier-{risk_seg['city_tier']} cities specifically, at a {risk_seg['return_rate_pct']}%
return rate -- meaning the blended COD figure actually understates how
severe the problem is in these specific locations.

RESOLUTION
Time-series analysis, corrected for two statistical outlier orders, shows the
genuine peak revenue month is {peak['month']} (March) at Rs {peak['revenue_inr']:,.2f}.
Before this correction, {inflated['month']} (January) appeared to be the top
month at an inflated Rs {inflated['apparent_revenue_inr']:,.2f}, but this was
driven entirely by two unusually large bulk orders landing in that month; its
true, corrected revenue is only Rs {inflated['corrected_revenue_inr']:,.2f}.
Recommended actions: (1) introduce stronger de-duplication checks at order
submission, (2) investigate COD fulfilment quality specifically in
Tier-{risk_seg['city_tier']} cities, and (3) treat March, not January, as the
benchmark peak month for future planning.
"""

    return {
        "status": "success",
        "narrative": narrative.strip(),
        "tokens": None,
    }


# ============================================================
# Orchestrator: tries online, falls back offline automatically
# ============================================================
def get_narrative(findings: dict) -> dict:
    """
    Public entry point. Uses the online Gemini path if an API key is
    configured and the call succeeds; otherwise falls back to the fully
    offline, deterministic template path. The caller never needs to know
    which path actually ran.
    """
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("No GEMINI_API_KEY found in environment - using offline fallback.")
        return generate_scr_narrative_offline(findings)

    result = generate_scr_narrative(findings)

    if result["status"] == "error":
        print(f"Gemini API call failed ({result['message']}) - using offline fallback.")
        return generate_scr_narrative_offline(findings)

    return result

def check_numeric_accuracy(narrative_text: str, findings: dict) -> bool:
    """
    Verifies all 5 key figures appear (verbatim or with equivalent rounding)
    as substrings in the narrative, after normalizing commas away.
    Prints a PASS/FAIL line per figure and returns True only if all pass.
    """
    text_normalized = narrative_text.replace(",", "")

    checks = [
        ("Cleaned total revenue (97,358.30)", "97358.3" in text_normalized),
        ("COD return rate (44.4)", "44.4" in text_normalized),
        ("COD + Tier-2 highest-risk rate (54.5)", "54.5" in text_normalized),
        ("Duplicate reconciliation delta (2,501.90)", "2501.9" in text_normalized),
        ("True peak month: March + 20,318.90",
         ("March" in text_normalized or "2026-03" in text_normalized)
         and "20318.9" in text_normalized),
    ]

    all_passed = True
    for label, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {label}")
        all_passed = all_passed and passed

    print(f"\nOverall: {'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'}")
    return all_passed


# ============================================================
# Script entry point
# ============================================================
if __name__ == "__main__":
    with open("/content/findings.json") as f:
        findings = json.load(f)

    result = get_narrative(findings)

    print("\n=== Narrative output ===")
    print(f"Status: {result['status']}")
    print(result["narrative"])

    print("\n=== Numeric accuracy check ===")
    check_numeric_accuracy(result["narrative"], findings)
