import google.generativeai as genai
from openai import OpenAI
import json

class AIService:
    def __init__(self, settings):
        self.provider = settings.provider
        self.api_key = settings.api_key
        self.learning_model = settings.learning_model
        self.scoring_model = settings.scoring_model

    def generate_rules(self, kept_items, deleted_items, current_rules=""):
        prompt = f"""
        You are an expert media curator. Analyze the user's library to understand their taste.
        
        Here are items the user explicitly KEPT:
        {json.dumps(kept_items, indent=2)}
        
        Here are items the user explicitly DELETED:
        {json.dumps(deleted_items, indent=2)}
        
        Current Rules (if any):
        {current_rules}
        
        Based on this data, generate a concise list of scoring rules that capture the user's preferences.
        Focus on genres, years, themes, keywords in overviews, and ratings.
        The output should be a plain text list of rules, one per line.
        Do not include introductory text, just the rules.
        """
        
        return self._call_model(prompt, model_type='learning')

    def score_items(self, items, rules):
        prompt = f"""
        You are an expert media curator. Score the following items based on these rules:
        
        RULES:
        {rules}
        
        ITEMS TO SCORE:
        {json.dumps(items, indent=2)}
        
        For each item, assign a score from 0 to 100, where 0 is a definite delete and 100 is a definite keep.
        Return the result as a JSON object where the keys are the item IDs (radarr_id or sonarr_id) and the values are the integer scores.
        Example format: {{ "123": 85, "456": 10 }}
        Do not include markdown formatting like ```json. Just the raw JSON string.
        """
        
        response_text = self._call_model(prompt, model_type='scoring')
        try:
            # Clean up potential markdown formatting
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from AI response: {response_text}")
            return {}

    def _call_model(self, prompt, model_type='learning'):
        model_name = self.learning_model if model_type == 'learning' else self.scoring_model
        
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
