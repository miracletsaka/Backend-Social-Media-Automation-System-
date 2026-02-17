from __future__ import annotations
import os
import json
from typing import Any

from openai import OpenAI
from fastapi import HTTPException

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_llm_json(prompt: str) -> dict[str, Any]:
    """
    Calls the LLM and STRICTLY returns JSON.
    Raises an error if JSON is invalid.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise JSON generator. You never include markdown or commentary."
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ],
            temperature=0.7,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM request failed: {e}")

    raw = response.choices[0].message.content.strip()

    try:
        return json.loads(raw)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "LLM did not return valid JSON",
                "raw_output": raw[:1000],
            },
        )
