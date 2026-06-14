"""Parse filters for Torque/PBS error messages."""

FILTERS: dict[str, str] = {
    r"PBS: job killed: node (\d+) \((\S+)\) requested job die, code (\d+)":
        "PBS JOB DIE REQUEST, node $2 code=$3",

    r"=>> PBS: job killed: node (\d+) \((\S+)\) requested job terminate, 'EOF' \(code (\d+)\) - internal or network failure attempting to communicate with sister MOM's":
        "PBS JOB KILLED request from $2 code=$3 due to communication failure, check status of nodes in this job",

    r"=>> PBS: job killed: node (\d+) \((\S+)\) requested job die, 'EOF' \(code (\d+)\) - internal or network failure attempting to communicate with sister MOM's":
        "PBS JOB DIE REQUEST due to communication failure to node $2 code=$3",

    r"PBS: job killed: walltime.*exceeded limit":
        "PBS JOB WALLTIME EXCEEDED",
}
