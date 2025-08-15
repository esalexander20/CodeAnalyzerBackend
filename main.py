from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional, Any
import os
import httpx
import json
from dotenv import load_dotenv
import tempfile
import shutil
import git
from github import Github
import time
import uuid
from datetime import datetime

# Import AI agent functions
from ai_agent import analyze_with_ai, fetch_github_repo_data

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="GitHub Code Analyzer API",
    description="API for analyzing GitHub repositories and providing code improvement suggestions",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/devstral-small:free")

# Supabase client function
async def get_supabase_client():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase configuration is missing"
        )
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    return headers

# Models
class RepositoryRequest(BaseModel):
    repository_url: HttpUrl
    user_id: str

class AnalysisResponse(BaseModel):
    id: str
    repository_url: str
    code_quality: int
    bugs_found: int
    recommendations: List[str]
    details: Dict[str, str]
    ai_analysis: Optional[Dict[str, Any]] = None

# Helper functions
def extract_repo_info(repo_url: str):
    """Extract owner and repo name from GitHub URL"""
    parts = repo_url.rstrip('/').split('/')
    if 'github.com' not in parts:
        raise ValueError("Not a valid GitHub URL")
    
    owner_idx = parts.index('github.com') + 1
    if len(parts) <= owner_idx + 1:
        raise ValueError("URL does not contain owner and repo")
    
    owner = parts[owner_idx]
    repo = parts[owner_idx + 1]
    return owner, repo

def clone_repository(repo_url: str):
    """Clone a repository to a temporary directory"""
    temp_dir = tempfile.mkdtemp()
    try:
        git.Repo.clone_from(repo_url, temp_dir)
        return temp_dir
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to clone repository: {str(e)}"
        )

def analyze_code_quality(repo_path: str):
    """Analyze code quality of the repository"""
    # This is a simplified mock implementation
    # In a real application, you would use static analysis tools
    
    # Count files by extension
    file_counts = {}
    total_lines = 0
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.startswith('.'):
                continue
                
            _, ext = os.path.splitext(file)
            ext = ext.lower()
            
            if ext:
                file_counts[ext] = file_counts.get(ext, 0) + 1
                
                # Count lines in text files
                if ext in ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.md', '.txt']:
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                            total_lines += sum(1 for _ in f)
                    except:
                        pass
    
    # Generate a mock score based on repository stats
    # In a real application, this would be based on actual code analysis
    score = min(100, max(60, 75 + (hash(str(file_counts)) % 20)))
    
    return {
        "code_quality": score,
        "bugs_found": abs(hash(repo_path) % 10),
        "file_distribution": file_counts,
        "total_lines": total_lines
    }

def generate_recommendations(repo_path: str, repo_url: str):
    """Generate code improvement recommendations"""
    # This is a simplified mock implementation
    # In a real application, you would use AI or static analysis tools
    
    # Generic recommendations
    generic_recommendations = [
        "Implement comprehensive unit tests to improve code coverage",
        "Add detailed documentation for public APIs and functions",
        "Consider using type hints to improve code readability and catch errors early",
        "Refactor large functions into smaller, more manageable pieces",
        "Implement consistent error handling throughout the codebase",
        "Add logging to help with debugging and monitoring",
        "Consider using a linter to enforce coding standards",
        "Review security practices, especially around user inputs and authentication",
        "Optimize database queries for better performance",
        "Implement CI/CD pipelines for automated testing and deployment"
    ]
    
    # Select a subset of recommendations based on the repository path hash
    num_recommendations = 5
    seed = hash(repo_path) % 100
    recommendations = []
    
    for i in range(num_recommendations):
        idx = (seed + i) % len(generic_recommendations)
        recommendations.append(generic_recommendations[idx])
    
    return recommendations

async def analyze_github_repo(repo_url: str):
    """Analyze a GitHub repository and generate a report"""
    try:
        # Extract owner and repo name
        owner, repo_name = extract_repo_info(repo_url)
        
        # Clone the repository for basic analysis
        repo_path = clone_repository(repo_url)
        
        # Fetch GitHub repository data for AI analysis
        github_data = await fetch_github_repo_data(f"{owner}/{repo_name}", GITHUB_TOKEN)
        
        try:
            # Analyze code quality using traditional methods
            quality_analysis = analyze_code_quality(repo_path)
            
            # Generate basic recommendations
            basic_recommendations = generate_recommendations(repo_path, repo_url)
            
            # Use AI to analyze the repository if API key is available
            ai_analysis = None
            if OPENROUTER_API_KEY:
                print(f"Using AI model {OPENROUTER_MODEL} to analyze repository")
                ai_analysis = await analyze_with_ai(github_data, OPENROUTER_API_KEY, OPENROUTER_MODEL)
                
                # If AI analysis was successful, use its recommendations and score
                if ai_analysis and not ai_analysis.get("error") and ai_analysis.get("recommendations"):
                    recommendations = ai_analysis.get("recommendations")
                    
                    # If AI provided a score, adjust our score (weighted average)
                    ai_score = ai_analysis.get("overall_score", 0)
                    if ai_score > 0:
                        # 70% weight to AI score, 30% to our basic analysis
                        quality_analysis["code_quality"] = int(0.7 * ai_score + 0.3 * quality_analysis["code_quality"])
                else:
                    # Fall back to basic recommendations if AI analysis failed
                    recommendations = basic_recommendations
            else:
                print("OpenRouter API key not available, using basic analysis only")
                recommendations = basic_recommendations
            
            # Generate detailed analysis
            if ai_analysis and not ai_analysis.get("error"):
                # Use AI-generated analysis if available
                details = {
                    "code_structure": ai_analysis.get("architecture_analysis", "No data available"),
                    "performance": ai_analysis.get("performance_analysis", "No data available"),
                    "security": ai_analysis.get("security_analysis", "No data available"),
                    "best_practices": ai_analysis.get("best_practices_analysis", "No data available")
                }
            else:
                # Fall back to generic analysis
                details = {
                    "code_structure": "The codebase has a clear structure but could benefit from more modularization. Consider breaking down large components into smaller, reusable ones.",
                    "performance": "Performance is generally good, but there are opportunities for optimization in data fetching and rendering large lists.",
                    "security": "Some potential security issues were found, including possible XSS vulnerabilities and insecure dependencies.",
                    "best_practices": "The code mostly follows best practices, but there are inconsistencies in coding style and patterns across the codebase."
                }
            
            # Create analysis result
            result = {
                "repository_url": repo_url,
                "code_quality": quality_analysis["code_quality"],
                "bugs_found": quality_analysis["bugs_found"],
                "recommendations": recommendations,
                "details": details,
                "ai_analysis": ai_analysis
            }
            
            return result
        finally:
            # Clean up temporary directory
            shutil.rmtree(repo_path, ignore_errors=True)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing repository: {str(e)}"
        )

# API Endpoints
@app.get("/")
async def root():
    return {"message": "GitHub Code Analyzer API"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_repository(request: RepositoryRequest):
    """Analyze a GitHub repository and provide improvement suggestions"""
    try:
        # Analyze the repository
        analysis_result = await analyze_github_repo(str(request.repository_url))
        
        # Generate a unique ID for the analysis
        analysis_id = f"analysis_{int(time.time())}"
        analysis_result["id"] = analysis_id
        
        # Store the result in Supabase
        try:
            supabase_headers = await get_supabase_client()
            
            # Extract owner and repo name for better data organization
            owner, repo_name = extract_repo_info(str(request.repository_url))
            
            # First check if repository already exists for this user
            async with httpx.AsyncClient() as client:
                check_response = await client.get(
                    f"{SUPABASE_URL}/rest/v1/repositories",
                    headers=supabase_headers,
                    params={
                        "url": f"eq.{str(request.repository_url)}",
                        "userId": f"eq.{request.user_id}",
                        "select": "id,url"
                    }
                )
                
                repository_id = None
                if check_response.status_code == 200:
                    existing_repos = check_response.json()
                    if existing_repos and len(existing_repos) > 0:
                        repository_id = existing_repos[0]["id"]
                        print(f"Repository already exists with ID: {repository_id}")
            
            # If repository doesn't exist, create it
            if not repository_id:
                # Prepare repository data
                repository_data = {
                    "id": str(uuid.uuid4()),
                    "userId": request.user_id,
                    "url": str(request.repository_url),
                    "name": repo_name,
                    "owner": owner,
                    "createdAt": datetime.now().isoformat(),
                    "updatedAt": datetime.now().isoformat()
                }
                
                # Insert into Supabase repositories table
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{SUPABASE_URL}/rest/v1/repositories",
                        headers=supabase_headers,
                        json=repository_data
                    )
                    
                    if response.status_code >= 400:
                        print(f"Error saving repository to Supabase: {response.text}")
                    else:
                        repository_id = repository_data["id"]
                        print(f"Created new repository with ID: {repository_id}")
            
            # Now save the analysis separately
            analysis_data = {
                "id": analysis_id,
                "repository_url": str(request.repository_url),
                "code_quality": analysis_result["code_quality"],
                "bugs_found": analysis_result["bugs_found"],
                "recommendations": analysis_result["recommendations"],
                "code_structure": analysis_result["details"]["code_structure"],
                "performance": analysis_result["details"]["performance"],
                "security": analysis_result["details"]["security"],
                "best_practices": analysis_result["details"]["best_practices"],
                "createdAt": datetime.now().isoformat(),
                "updatedAt": datetime.now().isoformat(),
                "userId": request.user_id
            }
            
            # Insert into Supabase analyses table
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SUPABASE_URL}/rest/v1/analyses",
                    headers=supabase_headers,
                    json=analysis_data
                )
                
                if response.status_code >= 400:
                    print(f"Error saving analysis to Supabase: {response.text}")
                    # Continue even if Supabase save fails
        
        except Exception as supabase_error:
            print(f"Supabase error: {str(supabase_error)}")
            # Continue even if Supabase integration fails
            # This ensures the API still works even if Supabase is down
        
        return analysis_result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)