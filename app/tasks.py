from app.celery_app import celery_app
from app.models import Staff, Shift, RosterAssignment
from app.optimizer import RosterOptimizer
from app.forecaster import StaffingForecaster
from app.compliance import ComplianceEngine
from app.rules import get_rules_for_country
from app.agent import SchedulingAgent
import mlflow
import os

# Ensure models are loaded for RAG/Compliance
compliance_engine = None

def get_compliance_engine():
    global compliance_engine
    if compliance_engine is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        laws_path = os.path.join(base_dir, "data", "laws")
        compliance_engine = ComplianceEngine()
        if os.path.exists(laws_path):
            compliance_engine.load_laws(laws_path)
    return compliance_engine


def init_mlflow():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mlflow_dir = os.path.join(base_dir, "mlruns")
    if not os.path.exists(mlflow_dir):
        os.makedirs(mlflow_dir)
    mlflow.set_tracking_uri(f"file:{mlflow_dir}")
    mlflow.set_experiment("SATS_Roster_Optimization")

@celery_app.task(name="app.tasks.task_optimize")
def task_optimize(staff_dicts, shift_dicts, country, rules, demand_signal):
    init_mlflow()
    staff = [Staff(**s) for s in staff_dicts]
    shifts = [Shift(**s) for s in shift_dicts]

    # Get Base Rules
    base_rules = get_rules_for_country(country)
    if rules:
        base_rules.update(rules)

    opt = RosterOptimizer(staff, shifts, base_rules, demand_signal=demand_signal)

    with mlflow.start_run():
        mlflow.log_param("country", country)
        mlflow.log_param("staff_count", len(staff))

        result = opt.solve()

        if not result:
            mlflow.log_metric("success", 0)
            return {"error": "Infeasible solution. Constraints are too tight for the number of staff."}

        metrics = result['metrics']
        mlflow.log_metric("success", 1)
        mlflow.log_metric("runtime", metrics['runtime_seconds'])

        # Serialize RosterAssignment list to dict
        result["assignments"] = [dict(a) for a in result["assignments"]]
        return result

@celery_app.task(name="app.tasks.task_forecast")
def task_forecast(shift_inputs, days, country, buffer):
    forecaster = StaffingForecaster()
    return forecaster.calculate_needs_simulation(
        shift_inputs,
        days,
        country=country,
        absence_buffer=buffer
    )

@celery_app.task(name="app.tasks.task_validate")
def task_validate(assignments, shift_definitions, country):
    init_mlflow()
    with mlflow.start_run():
        mlflow.log_param("endpoint", "validate")
        mlflow.log_param("country", country)

        rules = get_rules_for_country(country)
        opt = RosterOptimizer([], [], rules)
        technical_errors = opt.validate_roster(assignments, shift_definitions)

        engine = get_compliance_engine()
        audit_report = engine.audit_roster(assignments, shift_definitions, country_code=country)

        mlflow.log_metric("technical_errors", len(technical_errors))
        if audit_report:
            mlflow.log_metric("compliance_violations", len(audit_report.get("violations", [])))
            mlflow.log_param("verdict", audit_report.get("verdict", "N/A"))

        return {
            "technical_errors": technical_errors,
            "compliance_audit": audit_report
        }

@celery_app.task(name="app.tasks.task_recommend")
def task_recommend(date_target, shift_name, assignments, shift_definitions, staff_dicts, country):
    staff_list = [Staff(**s) for s in staff_dicts]
    rules = get_rules_for_country(country)
    opt = RosterOptimizer(staff_list, [], rules)
    suggestion = opt.recommend_replacement(
        date_target,
        shift_name,
        assignments,
        shift_definitions
    )
    return {"recommendation": suggestion}

@celery_app.task(name="app.tasks.task_agent_chat")
def task_agent_chat(message, state_dict):
    agent = SchedulingAgent()
    return agent.process_message(message, current_state_dict=state_dict)
