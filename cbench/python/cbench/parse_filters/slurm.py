"""Parse filters for Slurm error messages."""

FILTERS: dict[str, str] = {
    r"\* JOB.*CANCELLED.*DUE TO TIME LIMIT \*":
        "SLURM JOB WALLTIME EXCEEDED",

    r"\* JOB\s+(\S+)\s+CANCELLED .* DUE TO NODE FAILURE":
        "SLURM JOB $1 NODE FAILURE",

    r"\* JOB.*CANCELLED AT.*\d \*":
        "SLURM JOB CANCELLED",
}
