import sys

try:
    import ollama
except ImportError:
    print("ERROR: Ollama library not found. Please install it: pip install ollama", file=sys.stderr)
    ollama = None # Allow script to be imported, but functions will fail gracefully

# --- Configuration ---
DEFAULT_LLM_MODEL = "mistral:7b-instruct-q4_K_M" # Default model for testing

# --- Logging (Simple Print-Based) ---
def log_info(message: str):
    print(f"INFO: {message}", file=sys.stderr)

def log_error(message: str):
    print(f"ERROR: {message}", file=sys.stderr)

# --- LLM Test Function ---
def test_local_llm(prompt: str, model_name: str = DEFAULT_LLM_MODEL) -> str | None:
    """
    Sends a prompt to a local LLM served by Ollama and returns the response.

    Args:
        prompt (str): The prompt to send to the LLM.
        model_name (str, optional): The name of the Ollama model to use. 
                                    Defaults to DEFAULT_LLM_MODEL.

    Returns:
        str | None: The LLM's response content, or None if an error occurs.
    """
    if ollama is None:
        log_error("Ollama library is not available. Cannot communicate with LLM.")
        return None

    log_info(f"Sending prompt to Ollama model '{model_name}': '{prompt[:50]}...'")
    
    try:
        response = ollama.chat(
            model=model_name,
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                }
            ]
        )
        # Example response structure:
        # {
        #   'model': 'mistral:7b-instruct-q4_K_M',
        #   'created_at': '2023-12-19T18:01:57.953533Z',
        #   'message': {
        #     'role': 'assistant',
        #     'content': "The sky is blue due to a phenomenon called Rayleigh scattering..."
        #   },
        #   'done': True,
        #   ... (other stats)
        # }
        if response and 'message' in response and 'content' in response['message']:
            llm_content = response['message']['content']
            log_info(f"Received response from Ollama model '{model_name}'.")
            return llm_content
        else:
            log_error(f"Unexpected response structure from Ollama: {response}")
            return None
            
    except Exception as e:
        # This will catch various errors, including:
        # - Connection errors if Ollama server is not running (ollama._client.ConnectError)
        # - Errors if the model is not available (ollama._client.ResponseError, model not found)
        log_error(f"Error communicating with Ollama or model '{model_name}': {e}")
        if "model not found" in str(e).lower():
             log_error(f"Ensure you have pulled the model: `ollama pull {model_name}`")
        elif "connection refused" in str(e).lower() or "failed to connect" in str(e).lower():
             log_error("Ensure the Ollama server is running (e.g., `ollama serve` or via the desktop app).")
        return None

# --- Example Usage ---
if __name__ == '__main__':
    print("--- Testing Local LLM Interface ---")

    if ollama is None:
        print("Ollama Python library is not installed. Please run 'pip install ollama' to test this script.")
    else:
        test_prompt = "Why is the sky blue?"
        print(f"\nSending test prompt: '{test_prompt}' to model '{DEFAULT_LLM_MODEL}'")
        
        response_content = test_local_llm(test_prompt)
        
        if response_content:
            print("\nLLM Response:")
            print(response_content)
        else:
            print("\nNo response received or an error occurred. Check error messages above.")
            print("Please ensure:")
            print(f"  1. Ollama is installed and the server is running (e.g., `ollama serve` or via desktop app).")
            print(f"  2. The model '{DEFAULT_LLM_MODEL}' is downloaded (e.g., `ollama pull {DEFAULT_LLM_MODEL}`).")

        print("\n--- Testing with a non-existent model (expected failure) ---")
        non_existent_model = "nonexistent:model"
        test_prompt_2 = "Hello?"
        print(f"\nSending test prompt: '{test_prompt_2}' to model '{non_existent_model}'")
        response_content_2 = test_local_llm(test_prompt_2, model_name=non_existent_model)
        if response_content_2:
            print("\nLLM Response (unexpected for non-existent model):")
            print(response_content_2)
        else:
            print("\nNo response received for non-existent model, as expected (or error occurred).")

        print("\n--- LLM Interface Test Finished ---")
