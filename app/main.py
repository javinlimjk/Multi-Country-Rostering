# app/main.py
from fastapi import FastAPI, HTTPException, Security, status, Depends, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date
import os
import mlflow

import logging

# Import internal modules
from app.models import Staff, Shift, RosterAssignment

logger = logging.getLogger(__name__)
from app.optimizer import RosterOptimizer
from app.forecaster import StaffingForecaster
from app.compliance import ComplianceEngine
from app.rules import get_rules_for_country
from app.agent import SchedulingAgent
from app.demand_planner import FlightService, calculate_required_staff
from celery.result import AsyncResult
from app.celery_app import celery_app
from app.tasks import (
    task_forecast,
    task_optimize,
    task_validate,
    task_recommend,
    task_agent_chat
)

app = FastAPI(title="SATS Rostering API", version="6.0")

# --- SECURITY ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    return True

# --- GLOBAL STATE ---
@app.on_event("startup")
def load_models():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    laws_path = os.path.join(base_dir, "data", "laws")
    
    logger.info(f"🚀 Server Starting... Scanning for laws in {laws_path}")
    engine = ComplianceEngine()
    
    if os.path.exists(laws_path):
        engine.load_laws(laws_path)
    else:
        logger.warning("⚠️ Warning: Laws directory not found. RAG features will be disabled.")

    app.state.compliance_engine = engine

    # Setup MLflow
    mlflow_dir = os.path.join(base_dir, "mlruns")
    if not os.path.exists(mlflow_dir):
        os.makedirs(mlflow_dir)
    mlflow.set_tracking_uri(f"file:{mlflow_dir}")
    mlflow.set_experiment("SATS_Roster_Optimization")
    logger.info("✅ System Ready.")

def get_compliance_engine(request: Request):
    return getattr(request.app.state, "compliance_engine", None)

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
    date_target: Optional[date] = None
    shift_name: Optional[str] = None
    assignments: List[Dict[str, Any]]
    shift_definitions: List[Dict[str, Any]]
    staff_list: List[Staff]
    country: str 
    violation_type: Optional[str] = None
    violator: Optional[str] = None

class MetricsRequest(BaseModel):
    assignments: List[Dict[str, Any]]

class AgentChatRequest(BaseModel):
    message: str
    state: Optional[Dict[str, Any]] = None

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "active", "version": "6.0"}

@app.get("/tasks/{task_id}", dependencies=[Depends(verify_api_key)])
def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.state == 'PENDING':
        return {"state": task_result.state, "status": "Pending..."}
    elif task_result.state != 'FAILURE':
        return {
            "state": task_result.state,
            "result": task_result.result,
        }
    else:
        # something went wrong in the background job
        return {
            "state": task_result.state,
            "error": str(task_result.info), # this is the exception raised
        }

@app.post("/forecast", dependencies=[Depends(verify_api_key)])
def get_staffing_forecast(payload: ForecastRequest):
    task = task_forecast.delay(
        payload.shift_inputs, 
        payload.days, 
        payload.country,
        payload.buffer
    )
    return {"task_id": task.id}

@app.post("/optimize", dependencies=[Depends(verify_api_key)])
def generate_roster(payload: OptimizeRequest):
    staff_dicts = [s.dict() for s in payload.staff]
    shift_dicts = [s.dict() for s in payload.shifts]
    task = task_optimize.delay(
        staff_dicts,
        shift_dicts,
        payload.country,
        payload.rules,
        payload.demand_signal
    )
    return {"task_id": task.id}

@app.post("/validate", dependencies=[Depends(verify_api_key)])
def validate_roster(payload: ValidateRequest):
    task = task_validate.delay(
        payload.assignments,
        payload.shift_definitions,
        payload.country
    )
    return {"task_id": task.id}

@app.post("/recommend", dependencies=[Depends(verify_api_key)])
def recommend_staff(payload: RecommendationRequest):
    staff_dicts = [s.dict() for s in payload.staff_list]
    date_val = payload.date_target.isoformat() if payload.date_target and isinstance(payload.date_target, date) else payload.date_target
    task = task_recommend.delay(
        date_val,
        payload.shift_name, 
        payload.assignments, 
        payload.shift_definitions,
        staff_dicts,
        payload.country,
        payload.violation_type,
        payload.violator
    )
    return {"task_id": task.id}

@app.post("/metrics", dependencies=[Depends(verify_api_key)])
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
def search_laws(query: str, country: str = "SG", engine: Optional[Any] = Depends(get_compliance_engine)): # Added country param
    with mlflow.start_run():
        mlflow.log_param("endpoint", "search")
        mlflow.log_param("query", query)
        mlflow.log_param("country", country)

        if not engine:
            raise HTTPException(status_code=503, detail="AI Engine not ready")

        # Pass the country code to the engine
        results = engine.check_compliance(query, country_code=country)

        mlflow.log_metric("results_count", len(results))
        return results

@app.post("/agent/chat", dependencies=[Depends(verify_api_key)])
def agent_chat(payload: AgentChatRequest):
    task = task_agent_chat.delay(payload.message, payload.state)
    return {"task_id": task.id}

@app.get("/demand/{airport_code}", dependencies=[Depends(verify_api_key)])
def get_demand(airport_code: str):
    service = FlightService()
    flights = service.get_flights(airport_code)
    demand = calculate_required_staff(flights)
    return {"demand": demand}