"""Parse filters for OpenMPI error messages."""

FILTERS: dict[str, str] = {
    r"\[.*\]\[.*\]\s+from\s+(\S+) to:\s+(\S+)\s+error\s+polling.*with\s+status\s+(.*)status\s+number\s+(\d+)":
        "OMPI error '$3' with status $4 ($1 to $2)",

    r"\[(\S+):.*\]\s+pls:(.*)$":
        "OMPI says '$2' on $1",

    r"\[(\S+):.*\]\s+mca:.*component_find:\s+unable to open:\s+(\S+):":
        "OMPI could not load $2 on $1",

    r"Signal:(\d+)\s+(.*)$":
        "OMPI saw Signal $1 ($2)",

    r"An error occurred in MPI_Init":
        "OMPI says MPI_INIT failed",

    r"\[\d+,\d+,\d+\]\[(\S+)\]\s+(.*)":
        "OMPI says '$2'",

    r"Failed to find or execute the following executable":
        "OMPI says 'Failed to find or execute the executable",

    r"orterun noticed that \S+ rank (\d+) with PID (\d+) on node (\S+) exited on\s+(.*)$":
        "OMPI says orterun noticed rank $1 on node $3 exited with $4",

    r"orterun: killing job":
        "OMPI says orterun killing job",

    r"\[(\S+):\S+\] Error in ompi_mtl_mx_send,\s+(.*)$":
        "OMPI says 'Error in ompi_mtl_mx_send on $1, $2'",

    r"\[(\S+):\S+\] \*\*\* (An error occurred in.*)$":
        "OMPI says on node $1 '$2'",

    r"\[(\S+):\S+\] \*\*\* (MPI_.*)$":
        "OMPI says on node $1 '$2'",

    r"\[(\S+):\S+\] Error in mx_open_endpoint (\(.*\))":
        "OMPI says on node $1 'Error in mx_open_endpoint $2'",

    r"\[(\S+):\S+\].*(mca_oob_tcp_peer_try_connect:\s+connect to (\S+) failed:.*)$":
        "OMPI says on node $1 '$2'",

    r"\[(\S+):\S+\]\s+MPI_ABORT invoked on rank\s+(\S+)\s+in.*":
        "OMPI saw MPI_ABORT on node $1 (rank $2)",

    r"There are not enough slots on the nodes":
        "OMPI says not enough slots on the nodes to run as requested",

    r"There are not enough nodes in your allocation":
        "OMPI says not enough nodes to run as requested",

    r"A daemon \(.+\) died unexpectedly with status (\d+) while attempting":
        "OMPI says a daemon died (status $1)",

    r"Error name:\s+(\S+)":
        "OMPI saw error name $1",

    r"A daemon \(pid \S+\) died unexpectedly on (signal\s+\d+)\s+while attempting to":
        "OMPI says a daemon died ($1)",
}
