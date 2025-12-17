# While installing and running this system problems of llm can occur or others , that cannot be configured.
# If LLm is not working then run and see this script to see the problem and also how it works.
import json
import logging
import time
import requests
import re
from typing import Optional 

def _attempt_json_repair(text: str) -> Optional[dict]:
    """
    Try to fix common JSON formatting issues from LLM outputs.
    """
    if not text:
        return None

    # 1. First, try a clean parse (Best Case)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip Markdown Code Blocks (BEFORE Regex)
    # We do this on the full text to handle ```json wrapping
    clean_text = text.strip()
    if "```" in clean_text:
        clean_text = re.sub(r"```json", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"```", "", clean_text)
        clean_text = clean_text.strip()

    # 3. Extract JSON Object using Regex (The most robust method)
    # Finds the largest block starting with { and ending with }
    json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if json_match:
        candidate = json_match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # If that failed, try fixing trailing commas
            pass
    else:
        candidate = clean_text

    # 4. Last Resort: Fix Trailing Commas/Errors
    try:
        # Fix trailing commas in objects and arrays
        candidate = re.sub(r",\s*}", "}", candidate)
        candidate = re.sub(r",\s*]", "]", candidate)
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None

class MistralReasoningEngine:
    
    def enhance_report_with_llm(self, report: dict) -> dict:
        logging.info("🤖 Calling Ollama API for decision reasoning (Mistral model)...")

        # Build a smaller claim summary for the LLM
        claim_summary = {
            "patient_name": report.get("claim_info", {}).get("patient_name"),
            "diagnosis": report.get("medical_details", {}).get("diagnosis"),
            "claim_amount": report.get("financial_breakdown", {}).get("total_claimed"),
            "decision": report.get("final_decision", {}).get("status"),
            "reasons": report.get("final_decision", {}).get("review_reasons") or 
                       report.get("final_decision", {}).get("denial_reasons") or 
                       report.get("final_decision", {}).get("approval_reasons")
        }

        # Build the optimized JSON-only prompt (for /api/chat)
        system_prompt = (
            "You are a medical claims assistant. "
            "Return ONLY a valid JSON object with EXACT keys: "
            "decision, reasons (array). "
            "No markdown, no extra text, no explanations outside JSON."
        )
        
        user_prompt = f"""
        Analyze the following claim summary and explain the final decision.
        Respond ONLY in valid JSON.
        
        Claim summary:
        {json.dumps(claim_summary, indent=2)}
        """

        # Build the correct /api/chat payload
        payload = {
            "model": "mistral",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False
        }

        # Try twice ( if system fails then it will try twice )
        for attempt in range(2):
            try:
                # --- FIX: Use /api/chat endpoint ---
                response = requests.post(
                    "http://localhost:11434/api/chat",
                    json=payload,
                    timeout=240  # extended timeout
                )

                if response.status_code != 200:
                    raise Exception(f"Ollama returned {response.status_code}: {response.text}")

                resp_json = response.json()
                
                # --- FIX: Parse the /api/chat response ---
                content = None
                if isinstance(resp_json, dict) and resp_json.get("message"):
                    try:
                        content = resp_json["message"]["content"]
                    except (KeyError, TypeError):
                        pass
                
                if not content:
                    raise Exception("Ollama response missing 'message.content' key.")
                
                # --- FIX: Use robust JSON repair ---
                parsed = _attempt_json_repair(content)

                if not parsed or "reasons" not in parsed:
                    # This will log the bad JSON: "Expecting ',' delimiter..."
                    raise json.JSONDecodeError(f"LLM returned invalid schema: {content}", content, 0)

                report['final_decision']['llm_reasoning'] = parsed
                logging.info("✅ LLM reasoning added successfully.")
                break  # exit retry loop on success

            except Exception as e:
                logging.warning(f"⚠️ Attempt {attempt+1} failed ({e})")
                if attempt == 0:
                    logging.info("🔁 Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    logging.warning("⚠️ LLM returned invalid schema twice, using fallback.")
                    report['final_decision']['llm_reasoning'] = {
                        "decision": report.get("final_decision", {}).get("status", "UNDER_REVIEW"),
                        "reasons": ["Fallback reasoning used due to invalid LLM JSON."]
                    }

        return report
