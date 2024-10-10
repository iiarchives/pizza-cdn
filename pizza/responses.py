# Modules
from typing import List

# Property tables
SUCCESS = {
    "code": {"type": "integer", "title": "Status Code"},
    "url": {"type": "string", "title": "Public Image URL"}
}
FAIL = {
    "code": {"type": "integer", "title": "Status Code"},
    "message": {"type": "string", "title": "Error Message"}
}

# Handle generating response dicts
def generate_responses(codes: List[int]) -> dict:
    responses = {}
    for code in codes:
        properties = SUCCESS if code in range(200, 300) else FAIL
        responses[code] = {
            "content": {
                "application/json": {
                    "schema": {
                        "properties": properties,
                        "type": "object",
                        "required": list(properties.keys())
                    }
                }
            }
        }

    return responses
