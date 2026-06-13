"""Parse filters for MVAPICH/InfiniBand error messages."""

FILTERS: dict[str, str] = {
    r"Abort: .* code=VAPI_RETRY_EXC_ERR,.*dest rank=\[(\S+):\d+\]":
        "VAPI_RETRY_EXC_ERR, dest= $1",

    r"Abort: \[(\S+)[\:]*[\d+]*\]\s*[\:]*.*asynchronous event: (\S+) \((\S+)\)":
        "$2 ($3) on $1",

    r"Abort: .*asynchronous event: (\S+) \((\S+)\)":
        "$1 ($2)",

    r"Abort: \[(.*)\][ :]* .*Got completion with error, code=(\S+), vendor code=(\S+) dest rank=\[(\S+):\d+\]":
        "$2, dest= $4",

    r"Abort: VAPI_register_mr":
        "VAPI_register_mr ERROR",

    r"Abort:\s+\[(\S+)\].*HCA.*Local Catastrophic Error":
        "HCA Catasrophic on $1",

    r"Abort:\s+\[(\S+)\].*Cannot allocate CQ\s+(\(.*\))":
        "Cannot allocate CQ ($2) on $1",

    r"(\[\d+\]\s+setting QP.*NON-ACTIVE .*LID \d+)":
        "$1",

    r"\[(\d+)\]\s+Abort:\s+Cannot allocate CQ \(Generic error\)":
        "CQ (Generic error) task $1",

    r"(MPI.*Internal\s+MPI\s+error)":
        "$1",
}
