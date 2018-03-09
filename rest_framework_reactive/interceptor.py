import contextlib
import threading

from django.db.models.sql import compiler


class QueryInterceptor(object):
    """Django ORM query interceptor."""

    def __init__(self):
        self.intercepting_queries = 0
        self.tables = set()

    def _patch(self):
        """Monkey patch the SQLCompiler class to get all the referenced tables in a code block."""
        self.intercepting_queries += 1
        if self.intercepting_queries > 1:
            return

        self._original_as_sql = compiler.SQLCompiler.as_sql

        def as_sql(compiler, *args, **kwargs):
            try:
                return self._original_as_sql(compiler, *args, **kwargs)
            finally:
                self.tables.update(compiler.query.tables)

        compiler.SQLCompiler.as_sql = as_sql

    def _unpatch(self):
        """Restore SQLCompiler monkey patches."""

        self.intercepting_queries -= 1
        assert self.intercepting_queries >= 0

        if self.intercepting_queries:
            return

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
