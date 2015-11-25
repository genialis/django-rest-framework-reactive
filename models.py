# TODO: This should be moved to a separate application.
from .pool import pool
from resolwe.flow import models as flow_models, serializers as flow_serializers

# Register all the models with the query observer pool.
pool.register_model(flow_models.Project, flow_serializers.ProjectSerializer)
