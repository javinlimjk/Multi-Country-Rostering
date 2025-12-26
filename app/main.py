# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date
import os
import mlflow

# Import internal modules
from app.models import Staff, Shift, RosterAssignment
from app.optimizer import RosterOptimizer
from app.forecaster import StaffingForecaster
from app.compliance import ComplianceEngine
from app.rules import get_rules_for_country
from app.agent import SchedulingAgent

app = FastAPI(title="SATS Rostering API", version="6.0")

# --- GLOBAL STATE ---
compliance_engine = None

@app.on_event("startup")
def load_models():
    global compliance_engine
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    laws_path = os.path.join(base_dir, "data", "laws")
    
    print(f"🚀 Server Starting... Scanning for laws in {laws_path}")
    compliance_engine = ComplianceEngine()
    
    if os.path.exists(laws_path):
        compliance_engine.load_laws(laws_path)
    else:
        print("⚠️ Warning: Laws directory not found. RAG features will be disabled.")
    
    # Setup MLflow
    mlflow_dir = os.path.join(base_dir, "mlruns")
    if not os.path.exists(mlflow_dir):
        os.makedirs(mlflow_dir)
    mlflow.set_tracking_uri(f"file:{mlflow_dir}")
    mlflow.set_experiment("SATS_Roster_Optimization")
    print("✅ System Ready.")

# --- REQUEST SCHEMAS ---
class ForecastRequest(BaseModel):
    shift_inputs: List[Dict[str, Any]]
    days: int = 7
    country: str = "SG"
    buffer: float = 0.15

class OptimizeRequest(BaseModel):
    staff: List[Staff]
    shifts: List[Shift]
    country: str 
    rules: Optional[Dict[str, Any]] = None # Allow frontend to override rules

class ValidateRequest(BaseModel):
    assignments: List[Dict[str, Any]]
    shift_definitions: List[Dict[str, Any]]
    country: str

class RecommendationRequest(BaseModel):
    date_target: date
    shift_name: str
    assignments: List[Dict[str, Any]]
    shift_definitions: List[Dict[str, Any]]
    staff_list: List[Staff]
    country: str 

class MetricsRequest(BaseModel):
    assignments: List[Dict[str, Any]]

class AgentChatRequest(BaseModel):
    message: str

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "active", "version": "6.0"}

@app.post("/forecast")
def get_staffing_forecast(payload: ForecastRequest):
    forecaster = StaffingForecaster()
    return forecaster.calculate_needs_simulation(
        payload.shift_inputs, 
        payload.days, 
        country=payload.country, 
        absence_buffer=payload.buffer
    )

@app.post("/optimize")
def generate_roster(payload: OptimizeRequest):
    # 1. Get Base Rules
    rules = get_rules_for_country(payload.country)
    
    # 2. Apply Overrides (from Frontend "Advanced Policy" tab)
    if payload.rules:
        rules.update(payload.rules)

    print(f"Running Optimization for {len(payload.staff)} staff with rules: {rules}")

    opt = RosterOptimizer(payload.staff, payload.shifts, rules)
    
    # 3. Solve & Log
    with mlflow.start_run():
        mlflow.log_param("country", payload.country)
        mlflow.log_param("staff_count", len(payload.staff))
        
        result = opt.solve()
        
        if not result:
            mlflow.log_metric("success", 0)
            raise HTTPException(status_code=400, detail="Infeasible solution. Constraints are too tight for the number of staff.")
        
        metrics = result['metrics']
        mlflow.log_metric("success", 1)
        mlflow.log_metric("runtime", metrics['runtime_seconds'])
        
        return result 

@app.post("/validate")
def validate_roster(payload: ValidateRequest):
    rules = get_rules_for_country(payload.country)
    opt = RosterOptimizer([], [], rules) 
    # Pass dummy lists to init optimizer just for validation access
    errors = opt.validate_roster(payload.assignments, payload.shift_definitions)
    return {"errors": errors}

@app.post("/recommend")
def recommend_staff(payload: RecommendationRequest):
    rules = get_rules_for_country(payload.country)
    opt = RosterOptimizer(payload.staff_list, [], rules)
    suggestion = opt.recommend_replacement(
        payload.date_target, 
        payload.shift_name, 
        payload.assignments, 
        payload.shift_definitions
    )
    return {"recommendation": suggestion}

@app.post("/metrics")
def calculate_live_metrics(payload: MetricsRequest):
    # Convert simple dicts back to internal structure for calculation
    # We create dummy RosterAssignment objects
    assignments = []
    for x in payload.assignments:
        try:
            d = date.fromisoformat(x['date'])
            assignments.append(RosterAssignment(
                staff_id=x['staff_id'], 
                shift_id="manual", 
                date=d, 
                shift_type=x['shift']
            ))
        except: pass
    
    opt = RosterOptimizer([], [])
    return opt.calculate_metrics_only(assignments)

@app.get("/compliance/search")
def search_laws(query: str, country: str = "SG"): # Added country param
    if not compliance_engine:
        raise HTTPException(status_code=503, detail="AI Engine not ready")
    # Pass the country code to the engine
    return compliance_engine.check_compliance(query, country_code=country)

@app.post("/agent/chat")
def agent_chat(payload: AgentChatRequest):
    agent = SchedulingAgent()
    return agent.process_message(payload.message)