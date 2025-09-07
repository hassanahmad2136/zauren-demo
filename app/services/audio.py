import os
import json
from groq import Groq

def transcribe_audio(model_name: str, file_path: str):
    """
    Transcribe an audio file using the specified model.

    Parameters:
        model_name (str): The name of the model to use for transcription.
        file_path (str): The full path to the audio file.

    Returns:
        dict: The transcription result as a dictionary.
    """
    # Initialize the Groq client
    client = Groq()

    # Open the audio file
    with open(file_path, "rb") as file:
        # Create a transcription of the audio file
        transcription = client.audio.transcriptions.create(
            file=file,
            model=model_name,
            prompt="Specify context or spelling",
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language="en",
            temperature=0.0
        )
    
    # Print and return the transcription result
    print(json.dumps(transcription, indent=2, default=str))
    return transcription

# Example usage:
# transcribe_audio("whisper-large-v3-turbo", "path/to/YOUR_AUDIO.wav")
