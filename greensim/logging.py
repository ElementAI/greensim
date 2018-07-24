import logging

from greensim import now, local


class Filter(logging.Filter):
    """
    Logging filter that adds process-specific information to log records. By adding this filter to a logger enables
    using status variables `%(sim_time)f` and `%(sim_process)s` in format strings, so as to more easily track events
    within processes.
    """

    def filter(self, record: logging.LogRecord) -> int:
        try:
            sim_time = now()
            sim_process = local.name
        except TypeError:
            sim_time = -1.0
            sim_process = ""

        for attr, value in [
            ("sim_time", sim_time),
            ("sim_process", sim_process)
        ]:
            if not hasattr(record, attr):
                setattr(record, attr, value)

        return 1
