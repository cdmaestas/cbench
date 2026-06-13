"""Parse filters for Cray XE6/CLE error messages."""

FILTERS: dict[str, str] = {
    r"^\[NID (\S+)\] .*Apid \d+: (OOM.*)$":
        "ALPS NID $1: $2",

    r"aprun: Unexpected close":
        "APRUN Unexpected close of the apsys control connection",

    r"aprun: Exiting due to errors":
        "APRUN Exiting due to errors Application aborted",

    r"^\[(\d+)\] ERROR - (.*)$":
        "Rank $1 ERROR: $2",

    r"^Rank (\d+) \[.*\] \[(c\d\-\d.*)\] (.*)$":
        "Rank $1: $2 $3",

    r"PGFIO":
        "PGI Fortran IO errors",

    r"= Backtrace: =":
        "ALPS generated backtrace",

    r"PE \d+ exit signal Segmentation fault":
        "application segmentation fault",

    r"Failed to allocate memory for an unexpected message.\s+(\d+ unexpected messages queued)":
        "MPI unexpected message failure - $1",
}
