import contextlib
import threading

from django.db.models.sql import compiler

# Global interceptor lock.
INTERCEPTOR_LOCK = threading.Lock()


class QueryInterceptor(object):
    """Django ORM query interceptor."""

    def __init__(self):
        self.intercepting_queries = 0
        self.tables = set()
        self.thread = threading.current_thread()

    def _patch(self):
        """Monkey patch the SQLCompiler class to get all the referenced tables in a code block."""
        assert threading.current_thread() == self.thread

        self.intercepting_queries += 1
        if self.intercepting_queries > 1:
            return

        with INTERCEPTOR_LOCK:
            self._original_as_sql = compiler.SQLCompiler.as_sql

            def as_sql(compiler, *args, **kwargs):
                result = self._original_as_sql(compiler, *args, **kwargs)
                if threading.current_thread() != self.thread:
                    return result

                self.tables.update([table for table in compiler.query.tables if table != table.upper()])
                return result

            compiler.SQLCompiler.as_sql = as_sql

    def _unpatch(self):
        """Restore SQLCompiler monkey patches."""
        assert threading.current_thread() == self.thread

        self.intercepting_queries -= 1
        assert self.intercepting_queries >= 0

        if self.intercepting_queries:
            return

        with INTERCEPTOR_LOCK:
            compiler.SQLCompiler.as_sql = self._original_as_sql

    @contextlib.contextmanager
    def intercept(self, tables):
        """Intercept all tables used inside a codeblock.

        :param tables: Output tables set
        """
        self._patch()

        try:
            # Run the code block.
            yield
        finally:
            self._unpatch()
            # Collect intercepted tables.
            tables.update(self.tables)
