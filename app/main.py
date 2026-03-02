# app/main.py
from fastapi import FastAPI, HTTPException, Security, status, Depends
from fastapi.security import APIKeyHeader
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
from app.demand_planner import FlightService, calculate_required_staff

app = FastAPI(title="SATS Rostering API", version="6.0")

# --- SECURITY ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    # In production, check against env var or DB
    expected_key = os.getenv("COMPLIANCE_API_KEY")
    if not expected_key:
        return True # Dev mode: allow if key not set
    if api_key == expected_key:
        return True
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid API Key",
    )

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
    demand_signal: Optional[Dict[str, int]] = None # Time-series demand { "08:00": 15 }

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
    state: Optional[Dict[str, Any]] = None

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

    print(f"Running Optimization for {len(payload.staff)} staff")

    # Pass demand_signal to optimizer
    opt = RosterOptimizer(payload.staff, payload.shifts, rules, demand_signal=payload.demand_signal)
    
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

@app.post("/validate", dependencies=[Depends(verify_api_key)])
def validate_roster(payload: ValidateRequest):
    with mlflow.start_run():
        mlflow.log_param("endpoint", "validate")
        mlflow.log_param("country", payload.country)

        # 1. Technical Check (Hard Constraints) via Optimizer
        rules = get_rules_for_country(payload.country)
        opt = RosterOptimizer([], [], rules)
        technical_errors = opt.validate_roster(payload.assignments, payload.shift_definitions)

        # 2. AI Compliance Audit (Nuanced Checks)
        audit_report = None
        if compliance_engine:
            audit_report = compliance_engine.audit_roster(
                payload.assignments,
                payload.shift_definitions,
                country_code=payload.country
            )

        # Log metrics
        mlflow.log_metric("technical_errors", len(technical_errors))
        if audit_report:
            mlflow.log_metric("compliance_violations", len(audit_report.get("violations", [])))
            mlflow.log_param("verdict", audit_report.get("verdict", "N/A"))

        return {
            "technical_errors": technical_errors,
            "compliance_audit": audit_report
        }

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

@app.get("/compliance/search", dependencies=[Depends(verify_api_key)])
def search_laws(query: str, country: str = "SG"): # Added country param
    with mlflow.start_run():
        mlflow.log_param("endpoint", "search")
        mlflow.log_param("query", query)
        mlflow.log_param("country", country)

        if not compliance_engine:
            raise HTTPException(status_code=503, detail="AI Engine not ready")

        # Pass the country code to the engine
        results = compliance_engine.check_compliance(query, country_code=country)

        mlflow.log_metric("results_count", len(results))
        return results

@app.post("/agent/chat")
def agent_chat(payload: AgentChatRequest):
    agent = SchedulingAgent()
    return agent.process_message(payload.message, current_state_dict=payload.state)

@app.get("/demand/{airport_code}")
def get_demand(airport_code: str):
    service = FlightService()
    flights = service.get_flights(airport_code)
    demand = calculate_required_staff(flights)
    return {"demand": demand}