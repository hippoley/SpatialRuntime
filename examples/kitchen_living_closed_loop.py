from pprint import pprint

from spatialruntime.scenarios import run_kitchen_living_demo


if __name__ == "__main__":
    result = run_kitchen_living_demo()
    pprint({
        "case_id": result["case_id"],
        "trace_statuses": [trace["status"] for trace in result["traces"]],
        "final_runtime_state": result["final_runtime_state"],
    })
