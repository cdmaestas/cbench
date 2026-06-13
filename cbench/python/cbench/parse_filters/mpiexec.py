"""Parse filters for mpiexec error messages."""

FILTERS: dict[str, str] = {
    r"mpiexec:\s+Warning:\s+task\s+(\d+)\s+died\s+with\s+signal\s+(\S+)\s+\((.*)\)":
        "MPIEXEC WARNING: TASK DIED, signal ($3) from task $1",

    r"mpiexec:\s+Warning:\s+tasks\s+(\S+)\s+died\s+with\s+signal\s+(\S+)\s+\((.*)\)":
        "MPIEXEC WARNING: TASKS DIED, signal ($3) from tasks $1",

    r"mpiexec:\s+killall:\s+caught signal\s+(\S+)\s+\((.*)\)":
        "MPIEXEC KILLALL: signal ($2)",
}
