import contextlib
import threading

from django.db.models.sql import compiler

# Thread-local storage for intercepted tables.
INTERCEPTOR_TLS = threading.local()

_original_as_sql = compiler.SQLCompiler.as_sql
def intercept_as_sql(compiler, *args, **kwargs):
    result = _original_as_sql(compiler, *args, **kwargs)
    tables = getattr(INTERCEPTOR_TLS, 'tables', None)
    if tables is None:
        return result

    tables.update([table for table in compiler.query.tables if table != table.upper()])
    return result

# Monkey patch the SQLCompiler class to get all referenced tables in a code block.
compiler.SQLCompiler.as_sql = intercept_as_sql


class QueryInterceptor(object):
    """Django ORM query interceptor."""

    def __init__(self):
        self.tables = set()

    @contextlib.contextmanager
    def intercept(self, tables):
        """Intercept all tables used inside a codeblock.

        :param tables: Output tables set
        """
        global INTERCEPTOR_TLS

        INTERCEPTOR_TLS.tables = self.tables
        try:
            # Run the code block.
            yield
        finally:
            # Collect intercepted tables.
            tables.update(INTERCEPTOR_TLS.tables)
            del INTERCEPTOR_TLS.tables
