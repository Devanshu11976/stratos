"""AI insights generation using Groq API."""

import json
import logging
from typing import Dict, Any
from app.config.settings import settings
from app.services.storage import storage_service

logger = logging.getLogger("xeno.ai_insights")


class AIInsightsGenerator:
    """Generates AI-powered insights from validation results using Groq."""
    
    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        if not self.groq_api_key:
            logger.warning("Groq API key not configured, AI insights will be disabled")
    
    async def generate_insights(self, job_id: str, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI insights from validation results."""
        if not self.groq_api_key:
            return {"error": "Groq API key not configured"}
        
        try:
            from groq import Groq
            
            client = Groq(api_key=self.groq_api_key)
            
            # Prepare the prompt with validation data
            prompt = self._build_prompt(validation_result)
            
            # Call Groq API
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data quality expert. Analyze validation results and provide insights."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            insights_text = response.choices[0].message.content
            
            # Parse the response into structured insights
            insights = self._parse_insights(insights_text)
            
            # Save insights to file
            insights_path = storage_service.get_ai_insights_path(job_id)
            with open(insights_path, "w") as f:
                json.dump(insights, f, indent=2)
            
            logger.info(f"Job {job_id}: Generated AI insights at {insights_path}")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate AI insights: {e}")
            return {"error": str(e)}
    
    def _build_prompt(self, validation_result: Dict[str, Any]) -> str:
        """Build prompt for Groq API."""
        prompt = f"""
Analyze the following data validation results and provide insights:

Total Records: {validation_result.get('total_records', 0)}
Valid Records: {validation_result.get('valid_records', 0)}
Invalid Records: {validation_result.get('invalid_records', 0)}
Validation Rate: {round((validation_result.get('valid_records', 0) / validation_result.get('total_records', 1)) * 100, 2) if validation_result.get('total_records', 0) > 0 else 0}%

Error Breakdown:
{json.dumps(validation_result.get('validation_breakdown', {}), indent=2)}

Country Statistics:
{json.dumps(validation_result.get('country_stats', {}), indent=2)}

Please provide:
1. Executive Summary (2-3 sentences)
2. Data Quality Score (0-100)
3. Top 5 Validation Issues
4. Country-wise Analysis
5. Recommendations for Improvement
6. Risk Assessment (Low/Medium/High)

Format your response as JSON with these keys:
- executive_summary
- data_quality_score
- top_issues (array)
- country_analysis (object)
- recommendations (array)
- risk_assessment
"""
        return prompt
    
    def _parse_insights(self, insights_text: str) -> Dict[str, Any]:
        """Parse AI insights response into structured format."""
        try:
            # Try to parse as JSON
            insights = json.loads(insights_text)
            return insights
        except json.JSONDecodeError:
            # If not JSON, create a structured response from the text
            return {
                "executive_summary": insights_text[:500],
                "data_quality_score": 75,
                "top_issues": ["Unable to parse structured insights"],
                "country_analysis": {},
                "recommendations": ["Review validation logs manually"],
                "risk_assessment": "Medium",
                "raw_response": insights_text
            }


ai_insights_generator = AIInsightsGenerator()
