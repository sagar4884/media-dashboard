import google.generativeai as genai
from openai import OpenAI
import json
import time
import logging
from .logging_utils import log_message

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self, settings):
        self.provider = settings.provider
        self.api_key = settings.api_key
        self.learning_model = settings.learning_model
        self.scoring_model = settings.scoring_model

    def generate_rules(self, kept_items, deleted_items, current_rules=""):
        prompt = f"""
        You are an expert media curator. Analyze the user's library to understand their taste.
        
        Here are items the user explicitly KEPT (or watched via Tautulli):
        {json.dumps(kept_items, indent=2)}
        
        Here are items the user explicitly DELETED:
        {json.dumps(deleted_items, indent=2)}
        
        Current Rules (if any):
        {current_rules}
        
        Based on this data, identify patterns in the user's taste. Focus on genres, years, themes, keywords in overviews, and implied ratings.
        
        Instead of binary "Keep" or "Delete" rules, generate rules that influence the score (0-100).
        Use phrases like "Score higher for...", "Score lower for...", "Boost score if...", "Reduce score if...", "Slightly increase score for...".
        This allows for more nuanced scoring and incremental learning.
        
        Output a JSON object with two keys: "refinements" and "new_rules".
        
        "refinements": A list of objects where you modify an existing rule to be more accurate or convert a binary rule to a scoring rule.
        Format: {{ "original_rule": "...", "new_rule": "...", "reason": "..." }}
        
        "new_rules": A list of objects for completely new patterns you found.
        Format: {{ "rule": "...", "reason": "..." }}
        
        Example Output:
        {{
          "refinements": [
            {{
              "original_rule": "Keep Action Movies",
              "new_rule": "Score higher for Action Movies, especially if rated 7.0+",
              "reason": "User deletes low-rated action movies, so we should be more specific."
            }}
          ],
          "new_rules": [
            {{
              "rule": "Score lower for Holiday Movies",
              "reason": "User deleted 5 Christmas movies in this batch."
            }}
          ]
        }}
        
        Do not include markdown formatting like ```json. Just the raw JSON string.
        """
        
        log_message('DEBUG', f"AI Prompt (Learning):\n{prompt}", 'AI Curator')
        response_text = self._call_model(prompt, model_type='learning')
        log_message('DEBUG', f"AI Response (Learning):\n{response_text}", 'AI Curator')
        
        # Clean up potential markdown formatting
        cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
        return cleaned_text

    def score_items(self, items, rules):
        prompt = f"""
        You are an expert media curator. Score the following items based on these rules:
        
        SCORING RULES:
        {rules}
        
        ITEMS TO SCORE:
        {json.dumps(items, indent=2)}
        
        For each item, assign a score from 0 to 100 based on how well it fits the rules.
        - 0-20: Strong candidate for deletion (matches "Score lower" or "Delete" rules).
        - 80-100: Strong candidate for keeping (matches "Score higher" or "Keep" rules).
        - 40-60: Neutral or mixed signals.
        
        Return the result as a JSON object where the keys are the item IDs (radarr_id or sonarr_id) and the values are the integer scores.
        Example format: {{ "123": 85, "456": 10 }}
        Do not include markdown formatting like ```json. Just the raw JSON string.
        """
        
        log_message('DEBUG', f"AI Prompt (Scoring):\n{prompt}", 'AI Curator')
        response_text = self._call_model(prompt, model_type='scoring')
        log_message('DEBUG', f"AI Response (Scoring):\n{response_text}", 'AI Curator')

        try:
            # Clean up potential markdown formatting
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from AI response: {response_text}")
            return {}

    def _call_model(self, prompt, model_type='learning'):
        model_name = self.learning_model if model_type == 'learning' else self.scoring_model
        
        max_retries = 5
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                if self.provider == 'Gemini':
                    genai.configure(api_key=self.api_key)
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    return response.text
                    
                elif self.provider == 'OpenAI':
                    client = OpenAI(api_key=self.api_key)
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ]
                    )
                    return response.choices[0].message.content
                
                else:
                    raise ValueError(f"Unsupported provider: {self.provider}")
            
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Resource has been exhausted" in error_str:
                    if attempt < max_retries - 1:
                        sleep_time = base_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit (429). Retrying in {sleep_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.error("Max retries reached for AI service.")
                        raise Exception("AI Service Rate Limit Exceeded. Please check your API quota or try again later.") from e
                raise e
