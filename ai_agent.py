import os
import httpx
import json
from typing import Dict, List, Any, Optional
from github import Github
import base64

# OpenRouter API integration
async def analyze_with_ai(repo_data: Dict[str, Any], api_key: str, model: str = "mistralai/devstral-small:free") -> Dict[str, Any]:
    """
    Use OpenRouter API to analyze repository data with an AI model
    """
    if not api_key:
        print("Warning: OpenRouter API key not provided, skipping AI analysis")
        return {
            "error": "OpenRouter API key not configured",
            "recommendations": []
        }
    
    # Prepare the prompt for the AI
    system_prompt = """You are an expert software developer with deep knowledge of full-stack development, 
    best practices, design patterns, and code quality. Analyze the provided GitHub repository information 
    and provide detailed, actionable recommendations to improve the codebase. Focus on:
    
    1. Code structure and architecture
    2. Performance optimizations
    3. Security vulnerabilities
    4. Best practices and patterns
    5. Missing features or improvements
    
    Provide specific, actionable recommendations that would help improve the repository.
    """
    
    user_prompt = f"""
    Please analyze this GitHub repository and provide expert recommendations:
    
    Repository: {repo_data.get('full_name', 'Unknown')}
    Description: {repo_data.get('description', 'No description')}
    Language: {repo_data.get('language', 'Unknown')}
    Stars: {repo_data.get('stargazers_count', 0)}
    Forks: {repo_data.get('forks_count', 0)}
    Open Issues: {repo_data.get('open_issues_count', 0)}
    
    File structure:
    {json.dumps(repo_data.get('file_structure', []), indent=2)}
    
    README content:
    {repo_data.get('readme_content', 'No README found')}
    
    Key files content:
    {json.dumps(repo_data.get('key_files_content', {}), indent=2, default=str)[:4000]}
    
    Based on this information, provide:
    1. An overall assessment of code quality (score out of 100)
    2. A list of 5-10 specific recommendations to improve the codebase
    3. A brief analysis of architecture, performance, security, and best practices
    """
    
    try:
        # Call OpenRouter API
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github-analyzer.example.com",  # Replace with your actual domain
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
            )
            
            if response.status_code != 200:
                print(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "error": f"OpenRouter API error: {response.status_code}",
                    "recommendations": []
                }
            
            result = response.json()
            ai_content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Parse the AI response to extract structured data
            analysis_result = parse_ai_response(ai_content)
            return analysis_result
            
    except Exception as e:
        print(f"Error calling OpenRouter API: {str(e)}")
        return {
            "error": f"Error calling OpenRouter API: {str(e)}",
            "recommendations": []
        }

def parse_ai_response(ai_content: str) -> Dict[str, Any]:
    """
    Parse the AI response text into structured data
    """
    try:
        # Default structure
        result = {
            "overall_score": 0,
            "recommendations": [],
            "architecture_analysis": "",
            "performance_analysis": "",
            "security_analysis": "",
            "best_practices_analysis": "",
            "raw_response": ai_content
        }
        
        # Try to extract score (looking for patterns like "score: 75/100" or "75 out of 100")
        import re
        score_patterns = [
            r"(\d{1,3})\s*\/\s*100",  # Matches "75/100"
            r"(\d{1,3})\s*out of\s*100",  # Matches "75 out of 100"
            r"score:?\s*(\d{1,3})",  # Matches "score: 75" or "score 75"
            r"rating:?\s*(\d{1,3})",  # Matches "rating: 75"
            r"quality:?\s*(\d{1,3})"  # Matches "quality: 75"
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, ai_content, re.IGNORECASE)
            if match:
                try:
                    score = int(match.group(1))
                    if 0 <= score <= 100:
                        result["overall_score"] = score
                        break
                except ValueError:
                    continue
        
        # Extract recommendations (looking for numbered lists or bullet points)
        recommendations = []
        
        # Look for numbered recommendations
        numbered_pattern = r"\d+\.\s*(.*?)(?=\d+\.\s*|\Z|\n\n)"
        numbered_matches = re.findall(numbered_pattern, ai_content, re.DOTALL)
        if numbered_matches:
            recommendations.extend([rec.strip() for rec in numbered_matches if rec.strip()])
        
        # Look for bullet point recommendations
        bullet_pattern = r"[•\-\*]\s*(.*?)(?=[•\-\*]\s*|\Z|\n\n)"
        bullet_matches = re.findall(bullet_pattern, ai_content, re.DOTALL)
        if bullet_matches:
            recommendations.extend([rec.strip() for rec in bullet_matches if rec.strip()])
        
        # If we found recommendations, add them to the result
        if recommendations:
            result["recommendations"] = recommendations[:10]  # Limit to 10 recommendations
        
        # Extract analysis sections based on keywords
        sections = {
            "architecture_analysis": ["architecture", "structure", "organization", "design"],
            "performance_analysis": ["performance", "optimization", "speed", "efficiency"],
            "security_analysis": ["security", "vulnerability", "risk", "protection"],
            "best_practices_analysis": ["best practice", "convention", "standard", "pattern"]
        }
        
        for section_key, keywords in sections.items():
            for keyword in keywords:
                pattern = rf"(?i)(?:{keyword}[^.!?]*[.!?](?:[^.!?]*[.!?]){{0,3}})"
                matches = re.findall(pattern, ai_content)
                if matches:
                    result[section_key] = " ".join(matches)
                    break
        
        return result
        
    except Exception as e:
        print(f"Error parsing AI response: {str(e)}")
        return {
            "overall_score": 0,
            "recommendations": [],
            "error": f"Error parsing AI response: {str(e)}",
            "raw_response": ai_content
        }

async def fetch_github_repo_data(repo_url: str, github_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch repository data from GitHub API
    """
    try:
        owner, repo_name = repo_url.rstrip('/').split('/')[-2:]
        
        # Initialize GitHub client
        g = Github(github_token) if github_token else Github()
        
        # Get repository
        repo = g.get_repo(f"{owner}/{repo_name}")
        
        # Get basic repository info
        repo_data = {
            "full_name": repo.full_name,
            "description": repo.description,
            "language": repo.language,
            "stargazers_count": repo.stargazers_count,
            "forks_count": repo.forks_count,
            "open_issues_count": repo.open_issues_count,
            "file_structure": [],
            "readme_content": "",
            "key_files_content": {}
        }
        
        # Get README content
        try:
            readme = repo.get_readme()
            content = base64.b64decode(readme.content).decode('utf-8')
            repo_data["readme_content"] = content[:5000]  # Limit to 5000 chars
        except Exception as e:
            print(f"Error fetching README: {str(e)}")
        
        # Get file structure (top-level directories and files)
        try:
            contents = repo.get_contents("")
            file_structure = []
            
            for content_file in contents:
                file_structure.append({
                    "name": content_file.name,
                    "type": "dir" if content_file.type == "dir" else "file",
                    "path": content_file.path
                })
                
            repo_data["file_structure"] = file_structure
            
            # Get content of key files (package.json, requirements.txt, etc.)
            key_file_patterns = [
                "package.json", "requirements.txt", "setup.py", "pom.xml", "build.gradle",
                "Dockerfile", ".gitignore", "tsconfig.json", "composer.json"
            ]
            
            for pattern in key_file_patterns:
                for item in file_structure:
                    if item["name"] == pattern and item["type"] == "file":
                        try:
                            file_content = repo.get_contents(item["path"])
                            content = base64.b64decode(file_content.content).decode('utf-8')
                            repo_data["key_files_content"][item["name"]] = content[:2000]  # Limit to 2000 chars
                        except Exception as e:
                            print(f"Error fetching {pattern}: {str(e)}")
        
        except Exception as e:
            print(f"Error fetching repository structure: {str(e)}")
        
        return repo_data
        
    except Exception as e:
        print(f"Error fetching GitHub repository data: {str(e)}")
        return {
            "error": f"Error fetching GitHub repository data: {str(e)}"
        }
